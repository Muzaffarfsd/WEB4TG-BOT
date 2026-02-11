import asyncio
import logging
from typing import List, Dict, Optional
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from src.config import config
from src.knowledge_base import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def is_rate_limit_error(exception: BaseException) -> bool:
    error_msg = str(exception)
    return (
        "429" in error_msg 
        or "RATELIMIT_EXCEEDED" in error_msg
        or "quota" in error_msg.lower() 
        or "rate limit" in error_msg.lower()
        or (hasattr(exception, 'status') and exception.status == 429)
    )


class AIClient:
    def __init__(self):
        self._client = genai.Client(api_key=config.gemini_api_key)

    async def generate_response_stream(
        self,
        messages: List[Dict],
        thinking_level: str = "medium",
        on_chunk=None
    ) -> str:
        if thinking_level == "high":
            model = config.thinking_model_name
            gen_config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=4096)
            )
        else:
            model = config.fast_model_name
            gen_config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature
            )

        try:
            import queue
            chunk_queue = queue.Queue()

            def _stream_in_thread():
                full = ""
                try:
                    stream = self._client.models.generate_content_stream(
                        model=model,
                        contents=messages,
                        config=gen_config
                    )
                    for chunk in stream:
                        if chunk.text:
                            full += chunk.text
                            chunk_queue.put(full)
                except Exception:
                    pass
                finally:
                    chunk_queue.put(None)
                return full

            stream_task = asyncio.get_event_loop().run_in_executor(None, _stream_in_thread)

            full_text = ""
            while True:
                try:
                    partial = await asyncio.to_thread(chunk_queue.get, timeout=0.3)
                    if partial is None:
                        break
                    full_text = partial
                    if on_chunk:
                        try:
                            await on_chunk(full_text)
                        except Exception:
                            pass
                except Exception:
                    if stream_task.done():
                        while not chunk_queue.empty():
                            item = chunk_queue.get_nowait()
                            if item is None:
                                break
                            full_text = item
                            if on_chunk:
                                try:
                                    await on_chunk(full_text)
                                except Exception:
                                    pass
                        break

            result = await stream_task
            if result:
                full_text = result

            if full_text:
                return full_text
            return "Извините, не удалось сформировать ответ. Попробуйте переформулировать вопрос."
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            if is_rate_limit_error(e):
                logger.warning(f"Gemini stream rate limit: {error_type}: {error_msg}")
                return "Сейчас высокая нагрузка, попробуйте через минуту 🙏"
            logger.error(f"Gemini stream failed: {error_type}: {error_msg}")
            return await self.generate_response(messages, thinking_level)

    async def generate_response(
        self,
        messages: List[Dict],
        thinking_level: str = "medium",
        max_retries: int = 2,
        retry_delay: float = 0.5
    ) -> str:
        if thinking_level == "high":
            model = config.thinking_model_name
            gen_config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=4096)
            )
        else:
            model = config.fast_model_name
            gen_config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature
            )
        
        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=retry_delay, min=0.5, max=10),
            retry=retry_if_exception(is_rate_limit_error),
            reraise=True
        )
        async def _generate():
            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=model,
                contents=messages,
                config=gen_config
            )
            return response
        
        try:
            response = await _generate()
            
            if response.text:
                return response.text
            else:
                logger.warning("Empty response from Gemini")
                return "Извините, не удалось сформировать ответ. Попробуйте переформулировать вопрос."
                
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            if is_rate_limit_error(e):
                logger.warning(f"Gemini rate limit hit: {error_type}: {error_msg}")
                return "Сейчас высокая нагрузка, попробуйте через минуту 🙏"
            elif "timeout" in error_msg.lower() or "connect" in error_msg.lower():
                logger.error(f"Gemini connection error: {error_type}: {error_msg}")
                return "Не удалось подключиться к серверу. Попробуйте позже."
            else:
                logger.error(f"Gemini request failed: {error_type}: {error_msg}")
                return "Произошла техническая ошибка. Попробуйте ещё раз или напишите позже."
    
    async def generate_response_with_tools(
        self,
        messages: List[Dict],
        thinking_level: str = "medium",
        on_chunk=None
    ) -> dict:
        """Returns {"text": str, "tool_calls": list[dict], "all_tool_calls": list}"""
        try:
            model = config.fast_model_name
            tools = types.Tool(function_declarations=TOOL_DECLARATIONS)
            gen_config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=config.max_tokens,
                temperature=config.temperature,
                tools=[tools],
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode='AUTO')
                )
            )

            response = await asyncio.to_thread(
                self._client.models.generate_content,
                model=model,
                contents=messages,
                config=gen_config
            )

            tool_calls = []
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.function_call:
                        fc = part.function_call
                        tool_calls.append({
                            "name": fc.name,
                            "args": dict(fc.args) if fc.args else {}
                        })

            if tool_calls:
                return {"text": None, "tool_calls": tool_calls, "all_tool_calls": tool_calls}

            text = response.text if response.text else None
            return {"text": text, "tool_calls": [], "all_tool_calls": []}

        except Exception as e:
            logger.warning(f"Tool calling failed, falling back to regular response: {e}")
            fallback = await self.generate_response(messages, thinking_level)
            return {"text": fallback, "tool_calls": [], "all_tool_calls": []}

    async def agentic_loop(
        self,
        messages: List[Dict],
        tool_executor,
        thinking_level: str = "medium",
        max_steps: int = 4
    ) -> dict:
        """Multi-step agentic loop: AI calls tools, gets results, decides next action.
        
        Returns {"text": str, "special_actions": list, "all_tool_results": list}
        """
        all_tool_results = []
        special_actions = []
        current_messages = list(messages)
        
        for step in range(max_steps):
            result = await self.generate_response_with_tools(
                messages=current_messages,
                thinking_level=thinking_level
            )
            
            if not result["tool_calls"]:
                return {
                    "text": result["text"],
                    "special_actions": special_actions,
                    "all_tool_results": all_tool_results
                }
            
            step_tool_results = []
            for tc in result["tool_calls"]:
                try:
                    tool_result = await tool_executor(tc["name"], tc["args"])
                except Exception as e:
                    tool_result = f"Ошибка вызова инструмента {tc['name']}: {e}"
                    logger.error(f"Tool executor error for {tc['name']}: {e}")
                
                if not isinstance(tool_result, str):
                    tool_result = str(tool_result) if tool_result is not None else "Нет результата"
                
                if tool_result.startswith("[PORTFOLIO:"):
                    special_actions.append(("portfolio", tool_result))
                    step_tool_results.append(f"{tc['name']}: показано портфолио")
                elif tool_result == "[PRICING]":
                    special_actions.append(("pricing", None))
                    step_tool_results.append(f"{tc['name']}: показан прайс")
                elif tool_result == "[PAYMENT]":
                    special_actions.append(("payment", None))
                    step_tool_results.append(f"{tc['name']}: показана оплата")
                else:
                    step_tool_results.append(f"{tc['name']}: {tool_result}")
                    all_tool_results.append({"tool": tc["name"], "result": tool_result})
            
            tool_results_text = "\n\n".join(step_tool_results)
            current_messages.append({
                "role": "model",
                "parts": [{"text": f"Я вызвал инструменты. Результаты:\n{tool_results_text}"}]
            })
            current_messages.append({
                "role": "user",
                "parts": [{"text": "Проанализируй результаты. Если нужно — вызови ещё инструменты для полного ответа. Если данных достаточно — сформулируй финальный ответ клиенту."}]
            })
            
            logger.info(f"Agentic loop step {step+1}: {len(result['tool_calls'])} tool calls")
        
        final_response = await self.generate_response(
            messages=current_messages,
            thinking_level=thinking_level
        )
        
        return {
            "text": final_response,
            "special_actions": special_actions,
            "all_tool_results": all_tool_results
        }

    async def analyze_complex_query(
        self,
        query: str,
        context: Optional[str] = None
    ) -> str:
        prompt = query
        if context:
            prompt = f"Контекст: {context}\n\nВопрос: {query}"
        
        messages = [{"role": "user", "parts": [{"text": prompt}]}]
        return await self.generate_response(messages, thinking_level="high")
    
    async def quick_response(self, query: str) -> str:
        messages = [{"role": "user", "parts": [{"text": query}]}]
        return await self.generate_response(messages, thinking_level="low")


TOOL_DECLARATIONS = [
    {
        "name": "calculate_price",
        "description": "Рассчитать стоимость разработки Telegram Mini App по набору функций. Вызывай когда клиент спрашивает цену конкретного набора функций или хочет посчитать стоимость.",
        "parameters": {
            "type": "object",
            "properties": {
                "features": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Список функций: catalog, cart, auth, search, favorites, reviews, payments, subscriptions, installments, delivery, pickup, express, push, chat, video, loyalty, promo, referral, analytics, admin, crm, booking, queue, calendar, ai, ai_rec, auto_reply, smart_search, voice, tg_bot, whatsapp, maps, sms, email, 1c, api"
                }
            },
            "required": ["features"]
        }
    },
    {
        "name": "show_portfolio",
        "description": "Показать примеры работ из портфолио. Вызывай когда клиент хочет увидеть примеры, кейсы или портфолио.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["ecommerce", "services", "fintech", "education", "all"],
                    "description": "Категория портфолио"
                }
            },
            "required": ["category"]
        }
    },
    {
        "name": "show_pricing",
        "description": "Показать общий прайс-лист услуг. Вызывай когда клиент спрашивает о ценах в общем.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "create_lead",
        "description": "Создать заявку от клиента. Вызывай когда клиент говорит что хочет заказать, готов начать, просит связаться с ним.",
        "parameters": {
            "type": "object",
            "properties": {
                "interest": {
                    "type": "string",
                    "description": "Что интересует клиента"
                },
                "budget": {
                    "type": "string",
                    "description": "Примерный бюджет, если озвучен"
                }
            },
            "required": ["interest"]
        }
    },
    {
        "name": "show_payment_info",
        "description": "Показать реквизиты для оплаты. Вызывай когда клиент готов оплатить или спрашивает как оплатить.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "calculate_roi",
        "description": "Рассчитать окупаемость (ROI) Telegram Mini App для бизнеса клиента. Вызывай когда клиент сомневается в выгоде, спрашивает 'зачем мне это' или 'окупится ли'.",
        "parameters": {
            "type": "object",
            "properties": {
                "business_type": {
                    "type": "string",
                    "description": "Тип бизнеса: restaurant, shop, beauty, education, services, fitness, delivery, other"
                },
                "monthly_clients": {
                    "type": "integer",
                    "description": "Примерное количество клиентов в месяц"
                },
                "avg_check": {
                    "type": "integer",
                    "description": "Средний чек в рублях"
                }
            },
            "required": ["business_type"]
        }
    },
    {
        "name": "compare_plans",
        "description": "Сравнить тарифные планы и пакеты услуг. Вызывай когда клиент не может выбрать между вариантами или просит сравнение.",
        "parameters": {
            "type": "object",
            "properties": {
                "plan_type": {
                    "type": "string",
                    "enum": ["packages", "subscriptions", "custom_vs_template"],
                    "description": "Что сравнить: packages (MVP/Standard/Premium), subscriptions (подписки), custom_vs_template (заказная vs шаблон)"
                }
            },
            "required": ["plan_type"]
        }
    },
    {
        "name": "schedule_consultation",
        "description": "Записать клиента на бесплатную консультацию с менеджером. Вызывай когда клиент хочет обсудить проект подробнее, задаёт сложные вопросы или готов к созвону.",
        "parameters": {
            "type": "object",
            "properties": {
                "preferred_time": {
                    "type": "string",
                    "description": "Предпочитаемое время (если указано)"
                },
                "topic": {
                    "type": "string",
                    "description": "Тема консультации"
                }
            },
            "required": ["topic"]
        }
    },
    {
        "name": "generate_brief",
        "description": "Сгенерировать краткое ТЗ (бриф) на основе обсуждения с клиентом. Вызывай когда клиент описал свой проект и нужно резюмировать требования.",
        "parameters": {
            "type": "object",
            "properties": {
                "project_description": {
                    "type": "string",
                    "description": "Описание проекта клиента"
                },
                "features": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Список нужных функций"
                },
                "deadline": {
                    "type": "string",
                    "description": "Желаемые сроки"
                }
            },
            "required": ["project_description"]
        }
    },
    {
        "name": "check_discount",
        "description": "Проверить доступные скидки для клиента. Вызывай когда клиент спрашивает про скидки, акции, промокоды.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
]


ai_client = AIClient()

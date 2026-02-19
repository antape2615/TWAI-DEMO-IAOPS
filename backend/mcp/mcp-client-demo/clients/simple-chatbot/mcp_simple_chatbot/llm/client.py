import os, json
import boto3
from typing import List, Dict
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from .schemas import DecisionEnvelope, IntentEnvelope
from .prompts import SYSTEM_PROMPT_BASE, SYSTEM_PROMPT_CFN, CHAT_SYSTEM, INTENT_PROMPT
from botocore.config import Config
from botocore.exceptions import ClientError
import random, asyncio
import time
from collections import deque

DIAGRAM_TRIGGERS = ["diagrama", "diagram", "dibuja", "haz un diagrama", "ilustra", "visualiza", "esquema"]
INFRA_TRIGGERS = [
    "crea ", "crear ", "listar ", "lista ", "despliega", "desplegar", "elimina ",
    "actualiza ", "provisiona", " bucket", " lambda", " dynamodb", " ec2", " rds",
    "en mi cuenta", "cloudformation", "cloud control", "deploy",
]
TEXT_QUESTION_PREFIX = ("que ", "qué ", "cual", "cuál", "como ", "cómo ", "por qué", "porque ", "por que")


class RateLimiter:
    def __init__(self, max_calls: int, per_seconds: float):
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self.calls = deque()

    async def acquire(self):
        now = time.monotonic()
        while self.calls and now - self.calls[0] > self.per_seconds:
            self.calls.popleft()
        if len(self.calls) >= self.max_calls:
            sleep_for = self.per_seconds - (now - self.calls[0])
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
        self.calls.append(time.monotonic())

class LLMClient:
    def __init__(self, model_id=None, region=None):
        self.model_id = model_id or os.getenv("BEDROCK_MODEL")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        # Mejora los retries de botocore (aparte de los tuyos)
        br_config = Config(retries={"max_attempts": 10, "mode": "standard"})
        bedrock_runtime = boto3.client("bedrock-runtime", region_name=self.region, config=br_config)
        self._model = ChatBedrock(client=bedrock_runtime, 
                                  model_id=self.model_id,
                                  temperature=0.2, 
                                  max_tokens=2000)
        self._parser = PydanticOutputParser(pydantic_object=DecisionEnvelope)
        self._str_parser = StrOutputParser()
        self._rate = RateLimiter(max_calls=2, per_seconds=1.0)  # ejemplo 2 rps


    async def _safe_invoke(self, msgs, *, max_retries: int = 6, base_sleep: float = 0.5):
        """
        Invoca el modelo con reintentos exponenciales + jitter ante Throttling.
        Devuelve SIEMPRE texto plano (str) o levanta la última excepción si no es recuperable.
        """
        await self._rate.acquire()
        attempt = 0
        while True:
            try:
                # IMPORTANTE: ChatBedrock.invoke es síncrono; usa to_thread para no bloquear el event loop
                from functools import partial
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, partial(self._model.invoke, msgs))
                return self._str_parser.invoke(result)
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")
                if code in {"ThrottlingException", "Throttling", "TooManyRequestsException"} and attempt < max_retries:
                    # backoff exponencial con jitter
                    delay = (base_sleep * (2 ** attempt)) + random.uniform(0, 0.3)
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue
                raise
            except Exception:
                # Errores no recuperables (parseo, red, etc.)
                raise
    
    def _to_lc_messages(self, messages: List[Dict[str, str]]):
        out = []
        for m in messages:
            role = (m.get("role") or "").lower()
            content = m.get("content", "")
            if role == "system":
                out.append(SystemMessage(content=content))
            elif role == "assistant":
                out.append(AIMessage(content=content))
            else:
                out.append(HumanMessage(content=content))
        return out
    
    async def classify_intent(self, last_user: str) -> IntentEnvelope:
        parser = PydanticOutputParser(pydantic_object=IntentEnvelope)
        msgs = [
            SystemMessage(content="Eres un modelo estricto. Devuelve solo JSON."),
            HumanMessage(content=INTENT_PROMPT.replace("{consulta}", (last_user or "").strip()))
        ]
        raw = await self._safe_invoke(msgs)
        try:
            return parser.parse(raw)
        except Exception:
            return IntentEnvelope(intent="text", confidence=0.5, rationale="Fallback parse")

    async def classify_or_heuristic(self, last_user: str) -> IntentEnvelope:
        q = (last_user or "").strip().lower()
        # 1) Heurística rápida (0 coste)
        if any(t in q for t in DIAGRAM_TRIGGERS):
            return IntentEnvelope(intent="diagram", confidence=0.9, rationale="Heurística: verbo visual claro")
        if any(t in q for t in INFRA_TRIGGERS):
            return IntentEnvelope(intent="infrastructure", confidence=0.88, rationale="Heurística: verbo de infraestructura")
        if q.endswith("?") and q.startswith(TEXT_QUESTION_PREFIX):
            return IntentEnvelope(intent="text", confidence=0.9, rationale="Heurística: pregunta informativa")
        # 2) Si es ambiguo, llama al clasificador (1 invocación)
        return await self.classify_intent(q)

    async def get_response(self, messages: list[dict[str, str]]) -> str:
        last_user = ""
        for m in reversed(messages):
            if (m.get("role") or "").lower() == "user":
                last_user = (m.get("content") or "")
                break

        intent_env = await self.classify_or_heuristic(last_user)

        lc_msgs = self._to_lc_messages(messages)
        non_sys = [m for m in lc_msgs if not isinstance(m, SystemMessage)]
        if intent_env.intent in ("diagram", "both"):
            sys = SYSTEM_PROMPT_BASE.strip()
        elif intent_env.intent == "infrastructure":
            sys = SYSTEM_PROMPT_CFN.strip()
        else:
            sys = CHAT_SYSTEM.strip()
        call_msgs = [SystemMessage(content=sys)] + non_sys

        raw = await self._safe_invoke(call_msgs)
        try:
            env = self._parser.parse(raw)
        except Exception:
            env = DecisionEnvelope(decision="answer", answer=raw)
        return env.model_dump_json()
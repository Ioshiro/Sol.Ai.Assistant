import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

DEFAULT_BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:5077")
DEFAULT_API_KEY = os.getenv("OPENAI_API_KEY", "test-key")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "qwen/qwen3-8b")
DEFAULT_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "120"))


class OpenAIProtocolClient:
    def __init__(self, base_url: str, api_key: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def list_models(self) -> list[str]:
        payload = self._request_json("GET", "/v1/models")
        data = payload.get("data", [])
        return [item.get("id", "") for item in data if item.get("id")]

    def create_chat_completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
        tool_choice: str | None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if tool_choice:
            body["tool_choice"] = tool_choice

        return self._request_json("POST", "/v1/chat/completions", body)

    def stream_chat_completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
        tool_choice: str | None,
    ) -> str:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if tool_choice:
            body["tool_choice"] = tool_choice

        url = f"{self.base_url}/v1/chat/completions"
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(url=url, data=data, method="POST")
        request.add_header("Accept", "text/event-stream")
        request.add_header("Content-Type", "application/json")
        request.add_header("Authorization", f"Bearer {self.api_key}")

        chunks: list[str] = []

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                charset = response.headers.get_content_charset("utf-8") or "utf-8"

                for raw_line in response:
                    line = raw_line.decode(charset, errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue

                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break

                    chunk = json.loads(payload)
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue

                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if not isinstance(content, str) or not content:
                        continue

                    chunks.append(content)
                    print(content, end="", flush=True)

        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} su {url}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Impossibile raggiungere {url}: {exc.reason}") from exc

        return "".join(chunks).strip()

    def _request_json(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(url=url, data=data, method=method)
        request.add_header("Accept", "application/json")
        request.add_header("Content-Type", "application/json")
        request.add_header("Authorization", f"Bearer {self.api_key}")

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                charset = response.headers.get_content_charset("utf-8")
                raw = response.read().decode(charset)
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} su {url}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Impossibile raggiungere {url}: {exc.reason}") from exc


class ConsoleChat:
    def __init__(
        self,
        client: OpenAIProtocolClient,
        model: str,
        system_prompt: str | None,
        temperature: float | None,
        max_tokens: int | None,
        stream: bool,
        tool_choice: str | None,
    ) -> None:
        self.client = client
        self.model = model
        self.system_prompt = system_prompt.strip() if system_prompt else None
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.stream = stream
        self.tool_choice = tool_choice.strip() if tool_choice else None
        self.messages: list[dict[str, str]] = []
        self.reset()

    def reset(self) -> None:
        self.messages = []
        if self.system_prompt:
            self.messages.append({"role": "system", "content": self.system_prompt})

    def run(self) -> int:
        self._print_banner()

        while True:
            try:
                user_input = input("tu> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nUscita.")
                return 0

            if not user_input:
                continue

            if user_input.startswith("/"):
                if self._handle_command(user_input):
                    return 0
                continue

            self.messages.append({"role": "user", "content": user_input})

            try:
                if self.stream:
                    print("assistente> ", end="", flush=True)
                    assistant_message = self.client.stream_chat_completion(
                        model=self.model,
                        messages=self.messages,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        tool_choice=self.tool_choice,
                    )
                    print()
                else:
                    response = self.client.create_chat_completion(
                        model=self.model,
                        messages=self.messages,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        tool_choice=self.tool_choice,
                    )
                    assistant_message = self._extract_assistant_text(response)
                    print(f"assistente> {assistant_message}")
            except RuntimeError as exc:
                self.messages.pop()
                print()
                print(f"errore> {exc}")
                continue

            self.messages.append({"role": "assistant", "content": assistant_message})

    def _handle_command(self, command: str) -> bool:
        parts = command.split(maxsplit=1)
        action = parts[0].lower()
        argument = parts[1].strip() if len(parts) > 1 else ""

        if action in {"/exit", "/quit"}:
            print("Uscita.")
            return True

        if action == "/reset":
            self.reset()
            print("sessione> conversazione azzerata")
            return False

        if action == "/history":
            if not self.messages:
                print("sessione> nessun messaggio in cronologia")
                return False
            for index, message in enumerate(self.messages, start=1):
                print(f"{index:02d}. {message['role']}: {message['content']}")
            return False

        if action == "/model":
            if not argument:
                print(f"sessione> modello attuale: {self.model}")
                return False
            self.model = argument
            print(f"sessione> modello impostato a: {self.model}")
            return False

        if action == "/system":
            self.system_prompt = argument or None
            self.reset()
            stato = self.system_prompt if self.system_prompt else "disattivato"
            print(f"sessione> system prompt: {stato}")
            return False

        if action == "/stream":
            if not argument:
                stato = "on" if self.stream else "off"
                print(f"sessione> streaming: {stato}")
                return False
            lowered = argument.lower()
            if lowered in {"on", "true", "1"}:
                self.stream = True
                print("sessione> streaming attivato")
                return False
            if lowered in {"off", "false", "0"}:
                self.stream = False
                print("sessione> streaming disattivato")
                return False
            print("sessione> usa /stream on oppure /stream off")
            return False

        if action == "/toolchoice":
            if not argument:
                stato = self.tool_choice if self.tool_choice else "auto"
                print(f"sessione> tool_choice: {stato}")
                return False
            lowered = argument.lower()
            if lowered in {"auto", "none", "required"}:
                self.tool_choice = None if lowered == "auto" else lowered
                print(f"sessione> tool_choice impostato a: {lowered}")
                return False
            print("sessione> usa /toolchoice auto, /toolchoice required oppure /toolchoice none")
            return False

        if action == "/models":
            try:
                models = self.client.list_models()
            except RuntimeError as exc:
                print(f"errore> {exc}")
                return False
            if not models:
                print("sessione> nessun modello restituito dal servizio")
                return False
            print("sessione> modelli disponibili:")
            for model in models:
                print(f"- {model}")
            return False

        if action == "/help":
            self._print_commands()
            return False

        print("sessione> comando non riconosciuto. Usa /help")
        return False

    @staticmethod
    def _extract_assistant_text(response: dict[str, Any]) -> str:
        choices = response.get("choices") or []
        if not choices:
            return ""

        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()

        return json.dumps(response, ensure_ascii=False)

    def _print_banner(self) -> None:
        print("Chat console OpenAI-compatible")
        print(f"Endpoint: {self.client.base_url}")
        print(f"Modello: {self.model}")
        print(f"Streaming: {'on' if self.stream else 'off'}")
        print(f"Tool choice: {self.tool_choice or 'auto'}")
        if self.system_prompt:
            print(f"System: {self.system_prompt}")
        self._print_commands()

    @staticmethod
    def _print_commands() -> None:
        print("Comandi: /help, /models, /model [nome], /system [testo], /stream [on|off], /toolchoice [auto|required|none], /reset, /history, /exit")


def resolve_model(client: OpenAIProtocolClient, requested_model: str | None) -> str:
    if requested_model:
        return requested_model

    try:
        models = client.list_models()
    except RuntimeError:
        return DEFAULT_MODEL

    if models:
        return models[0]

    return DEFAULT_MODEL


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Chat in console contro un endpoint OpenAI-compatible (/v1/chat/completions)."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL del servizio, es. http://localhost:5077")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="API key da inviare come Bearer token")
    parser.add_argument("--model", help="Modello da usare; se omesso prova a leggerlo da /v1/models")
    parser.add_argument("--system", help="System prompt iniziale")
    parser.add_argument("--temperature", type=float, default=0.2, help="Temperature della richiesta")
    parser.add_argument("--tool-choice", choices=["auto", "required", "none"], default="auto", help="Tool choice da inviare alla request")
    parser.add_argument("--max-tokens", type=int, help="Max tokens della risposta")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Timeout HTTP in secondi")
    parser.add_argument("--no-stream", action="store_true", help="Disattiva lo streaming e usa la risposta completa")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    client = OpenAIProtocolClient(
        base_url=args.base_url,
        api_key=args.api_key,
        timeout=args.timeout,
    )
    model = resolve_model(client, args.model)

    chat = ConsoleChat(
        client=client,
        model=model,
        system_prompt=args.system,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        stream=not args.no_stream,
        tool_choice=None if args.tool_choice == "auto" else args.tool_choice,
    )
    return chat.run()


if __name__ == "__main__":
    sys.exit(main())

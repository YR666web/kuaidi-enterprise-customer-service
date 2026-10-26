"""对真实聊天接口进行并发压测，并输出可归档的 JSON 报告。"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from statistics import mean

import httpx


def percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(round((len(ordered) - 1) * ratio), len(ordered) - 1)], 2)


def one_request(base_url: str, token: str, message: str, index: int) -> dict:
    started = time.perf_counter()
    first_token_ms: float | None = None
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"session_id": f"load-{int(time.time() * 1000)}-{index}", "message": message}
    try:
        with httpx.Client(timeout=90.0) as client:
            with client.stream(
                "POST", f"{base_url.rstrip('/')}/api/v1/chat/stream", headers=headers, json=payload
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line.startswith("data:") and first_token_ms is None:
                        data = json.loads(line.removeprefix("data:").strip())
                        if data.get("delta"):
                            first_token_ms = (time.perf_counter() - started) * 1000
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "latencyMs": round((time.perf_counter() - started) * 1000, 2),
        }
    return {
        "ok": True,
        "firstTokenMs": round(first_token_ms, 2) if first_token_ms else None,
        "latencyMs": round((time.perf_counter() - started) * 1000, 2),
    }


def run(args: argparse.Namespace) -> dict:
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [
            pool.submit(one_request, args.base_url, args.token, args.message, i)
            for i in range(args.requests)
        ]
        results = [future.result() for future in as_completed(futures)]
    successes = [item for item in results if item["ok"]]
    first_tokens = [item["firstTokenMs"] for item in successes if item["firstTokenMs"] is not None]
    latencies = [item["latencyMs"] for item in successes]
    return {
        "baseUrl": args.base_url, "requests": args.requests, "concurrency": args.concurrency,
        "success": len(successes), "failed": args.requests - len(successes),
        "successRate": round(len(successes) / args.requests, 4) if args.requests else 0.0,
        "elapsedMs": round((time.perf_counter() - started) * 1000, 2),
        "firstTokenMs": {
            "p50": percentile(first_tokens, 0.5),
            "p95": percentile(first_tokens, 0.95),
            "p99": percentile(first_tokens, 0.99),
        },
        "latencyMs": {
            "mean": round(mean(latencies), 2) if latencies else None,
            "p50": percentile(latencies, 0.5),
            "p95": percentile(latencies, 0.95),
            "p99": percentile(latencies, 0.99),
        },
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="StackLang SSE 并发压测")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--token", required=True, help="JWT；不会写入报告")
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--message", default="你好")
    parser.add_argument("--report", type=Path, help="JSON 报告输出路径")
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("requests 和 concurrency 必须为正整数")
    rendered = json.dumps(run(args), ensure_ascii=False, indent=2)
    print(rendered)
    if args.report:
        args.report.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()

from langchain_core.messages import AIMessage, HumanMessage

from app.agent.responder import CustomerServiceResponder


def test_responder_passes_history_and_facts_to_model() -> None:
    class FakeModel:
        def invoke(self, prompt: str):
            assert "客户：查快递" in prompt
            assert "无实时物流数据" in prompt
            return AIMessage(content="我目前不能核验该单号的实时轨迹。")

    responder = CustomerServiceResponder()
    responder._models["fast"] = FakeModel()
    reply = responder.reply(
        "是真的吗？",
        [HumanMessage(content="查快递")],
        verified_result="无实时物流数据",
    )
    assert reply == "我目前不能核验该单号的实时轨迹。"


def test_responder_streams_model_chunks() -> None:
    class FakeModel:
        def stream(self, prompt: str, config=None):
            assert "客户：你好" in prompt
            yield AIMessage(content="你")
            yield AIMessage(content="好")

    responder = CustomerServiceResponder()
    responder._models["fast"] = FakeModel()
    assert list(responder.stream_reply("你好", [])) == ["你", "好"]

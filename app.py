"""Streamlit UI — thin layer over core.pipeline."""
import streamlit as st
from core import config
from core.pipeline import ask, PipelineResult
from core.sql_guard import GuardError
from core.llm import prewarm

st.set_page_config(page_title="VizQuery", page_icon="📊", layout="wide")

EXAMPLE_QUESTIONS = [
    "Show monthly revenue for the last 6 months",
    "Top 5 restaurants by number of orders",
    "Split of payment methods",
    "Average delivery time by zone for delivered orders",
    "How many orders were placed in total?",
    "Which cuisine type has the highest average rating?",
]

# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Settings")
    model = st.selectbox("Model", config.ALL_MODELS, index=0)

    st.markdown("---")
    st.subheader("Example questions")
    for q in EXAMPLE_QUESTIONS:
        if st.button(q, width='stretch'):
            st.session_state["prefill"] = q

# --- Pre-warm model once per session ---
if "warmed" not in st.session_state:
    with st.spinner(f"Loading {model} into memory…"):
        prewarm(model)
    st.session_state["warmed"] = True

# --- Header ---
st.title("📊 VizQuery")
st.caption("Ask a question about the Karachi food delivery platform — get a chart.")

# --- Chat history ---
if "history" not in st.session_state:
    st.session_state["history"] = []

for entry in st.session_state["history"]:
    with st.chat_message(entry["role"]):
        if entry["role"] == "user":
            st.write(entry["content"])
        else:
            _r: PipelineResult = entry["result"]
            if _r.fig:
                st.plotly_chart(_r.fig, width='stretch')
            elif not _r.df.empty:
                st.dataframe(_r.df, width='stretch')
            else:
                st.info("No data matched your query.")
            with st.expander("View SQL & details"):
                st.code(_r.sql, language="sql")
                st.markdown(f"**Reasoning:** {_r.plan.reasoning}")
                st.markdown(
                    f"**Latency:** LLM {_r.llm_latency:.2f}s · SQL {_r.sql_latency:.3f}s · "
                    f"Total {_r.llm_latency + _r.sql_latency:.2f}s"
                    + (" _(retried)_" if _r.retried else "")
                )

# --- Input ---
prefill = st.session_state.pop("prefill", "")
question = st.chat_input("Ask a question about your data…")
if not question and prefill:
    question = prefill

if question:
    st.session_state["history"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                result = ask(question, model=model)
                if result.fig:
                    st.plotly_chart(result.fig, width='stretch')
                elif not result.df.empty:
                    st.dataframe(result.df, width='stretch')
                else:
                    st.info("No data matched your query.")
                with st.expander("View SQL & details"):
                    st.code(result.sql, language="sql")
                    st.markdown(f"**Reasoning:** {result.plan.reasoning}")
                    st.markdown(
                        f"**Latency:** LLM {result.llm_latency:.2f}s · SQL {result.sql_latency:.3f}s · "
                        f"Total {result.llm_latency + result.sql_latency:.2f}s"
                        + (" _(retried)_" if result.retried else "")
                    )
                st.session_state["history"].append({"role": "assistant", "result": result})
            except GuardError as e:
                msg = "I generated an unsafe or invalid query. Try rephrasing your question."
                st.error(msg)
                st.caption(f"Guard detail: {e}")
            except Exception as e:
                st.error(f"Unexpected error: {e}")

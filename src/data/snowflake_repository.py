"""
Snowflake data repository for Resilience Rewired.

Fills the same nine tables as LocalDataRepository from RESILIENCE_REWIRED_DB.RAW, so every
Python calculation, test and page runs unchanged on Snowflake data. Adds what only Snowflake
has: model stress scores, the deterministic shock function and the Cortex Agent.
All SQL uses bind parameters; nothing user-typed is ever formatted into SQL or a shell.
"""

import json
import os
from typing import Any, Dict, List, Optional

import pandas as pd

from src.data.local_repository import LocalDataRepository
from config.settings import SNOWFLAKE_DATABASE, SNOWFLAKE_WAREHOUSE

AGENT_NAME = f"{SNOWFLAKE_DATABASE}.SEMANTIC.RESILIENCE_INTELLIGENCE_AGENT"

# Original CSV columns, in source order. Dates come back as text, exactly as pandas reads the CSVs.
RAW_TABLES = {
    "accounts": ("ACCOUNTS_RAW", "account_id, district_id, frequency, TO_VARCHAR(account_opened) AS account_opened"),
    "clients": ("CLIENTS_RAW", "client_id, gender, TO_VARCHAR(birth_date) AS birth_date, district_id"),
    "dispositions": ("DISPOSITIONS_RAW", "disposition_id, client_id, account_id, type"),
    "cards": ("CARDS_RAW", "card_id, disposition_id, card_type, TO_VARCHAR(issued) AS issued"),
    "districts": ("DISTRICTS_RAW", "* EXCLUDE (_source_file, _loaded_at)"),
    "loans": ("LOANS_RAW", "loan_id, account_id, TO_VARCHAR(loan_start) AS loan_start, amount, duration_months, "
                           "monthly_payment, status, status_meaning, defaulted"),
    "standing_orders": ("STANDING_ORDERS_RAW", "order_id, account_id, to_bank, to_account, amount, purpose"),
    "monthly_summary": ("MONTHLY_SUMMARY_RAW", "* EXCLUDE (_source_file, _loaded_at)"),
}


class SnowflakeDataRepository(LocalDataRepository):
    _instance = None

    def __init__(self, connection_name: Optional[str] = None):
        super().__init__()
        self.connection_name = connection_name or os.getenv("SNOWFLAKE_CONNECTION_NAME", "datathon")
        self._conn = None
        self.is_connected = False
        self.connection_error: Optional[str] = None
        self.stress_scores: Optional[pd.DataFrame] = None
        self.model_metrics: Optional[pd.DataFrame] = None
        self.model_calibration: Optional[pd.DataFrame] = None
        self.anomalies: Optional[pd.DataFrame] = None
        self.balance_forecast: Optional[pd.DataFrame] = None
        self.forecast_backtest: Optional[pd.DataFrame] = None
        self.vulnerability_drivers: Optional[pd.DataFrame] = None

    @classmethod
    def get_instance(cls, connection_name: Optional[str] = None) -> "SnowflakeDataRepository":
        if cls._instance is None:
            cls._instance = cls(connection_name)
            cls._instance.load_all()
        return cls._instance

    # ------------------------------------------------------------------ connection
    def _connect(self):
        import snowflake.connector

        last_error = None

        # 1. Try Streamlit Secrets (for Streamlit Community Cloud)
        try:
            import streamlit as st

            sec = None
            if hasattr(st, "secrets"):
                if "connections" in st.secrets and "snowflake" in st.secrets["connections"]:
                    sec = dict(st.secrets["connections"]["snowflake"])
                elif "snowflake" in st.secrets:
                    sec = dict(st.secrets["snowflake"])

            if sec:
                account = sec.get("account")
                user = sec.get("user") or sec.get("username")
                password = sec.get("password")
                role = sec.get("role", "ACCOUNTADMIN")
                warehouse = sec.get("warehouse", SNOWFLAKE_WAREHOUSE)
                database = sec.get("database", SNOWFLAKE_DATABASE)
                schema = sec.get("schema", "APP")
                self._conn = snowflake.connector.connect(
                    account=account,
                    user=user,
                    password=password,
                    role=role,
                    warehouse=warehouse,
                    database=database,
                    schema=schema,
                    client_session_keep_alive=True,
                )
                return
        except Exception as e:
            last_error = e

        # 2. Try native Streamlit in Snowflake session (st.connection("snowflake"))
        try:
            import streamlit as st

            self._conn = st.connection("snowflake").raw_connection
            cur = self._conn.cursor()
            try:
                cur.execute(f"USE DATABASE {SNOWFLAKE_DATABASE}")
                cur.execute(f"USE WAREHOUSE {SNOWFLAKE_WAREHOUSE}")
            finally:
                cur.close()
            return
        except Exception as e:
            last_error = e

        # 3. Try explicit environment variables
        if os.getenv("SNOWFLAKE_ACCOUNT") and os.getenv("SNOWFLAKE_USER") and os.getenv("SNOWFLAKE_PASSWORD"):
            try:
                self._conn = snowflake.connector.connect(
                    account=os.getenv("SNOWFLAKE_ACCOUNT"),
                    user=os.getenv("SNOWFLAKE_USER"),
                    password=os.getenv("SNOWFLAKE_PASSWORD"),
                    role=os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
                    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", SNOWFLAKE_WAREHOUSE),
                    database=os.getenv("SNOWFLAKE_DATABASE", SNOWFLAKE_DATABASE),
                    schema=os.getenv("SNOWFLAKE_SCHEMA", "APP"),
                    client_session_keep_alive=True,
                )
                return
            except Exception as e:
                last_error = e

        # 4. Try named connections from Snowflake CLI (config.toml / connections.toml)
        conn_names = []
        if self.connection_name:
            conn_names.append(self.connection_name)
        for name in ["datathon", "default"]:
            if name not in conn_names:
                conn_names.append(name)

        for c_name in conn_names:
            try:
                self._conn = snowflake.connector.connect(
                    connection_name=c_name,
                    database=SNOWFLAKE_DATABASE,
                    warehouse=SNOWFLAKE_WAREHOUSE,
                    client_session_keep_alive=True,
                )
                return
            except Exception as e:
                last_error = e

        if last_error:
            raise last_error

    def query(self, sql: str, params: Optional[tuple] = None) -> pd.DataFrame:
        cur = self._conn.cursor()
        try:
            cur.execute(sql, params)
            df = cur.fetch_pandas_all()
        finally:
            cur.close()
        df.columns = [c.lower() for c in df.columns]
        return df

    def _scalar(self, sql: str, params: tuple):
        cur = self._conn.cursor()
        try:
            cur.execute(sql, params)
            return cur.fetchone()[0]
        finally:
            cur.close()

    # ------------------------------------------------------------------ loading
    def load_all(self):
        if self._is_loaded:
            return
        try:
            self._connect()
            for attr, (table, columns) in RAW_TABLES.items():
                setattr(self, attr, self.query(f"SELECT {columns} FROM RAW.{table}"))
            self.stress_scores = self.query(
                "SELECT account_id, as_of_month, stress_probability, risk_tier, primary_risk_driver, top_drivers "
                "FROM ML.ACCOUNT_STRESS_SCORES"
            ).set_index("account_id")
            self.model_metrics = self.query("SELECT * FROM ML.MODEL_EVALUATION_METRICS")
            self.model_calibration = self.query("SELECT * FROM ML.MODEL_CALIBRATION ORDER BY bin")
            self._load_ml_function_outputs()
            self._prepare_frames()
            self._is_loaded = True
            self.is_connected = True
        except Exception as error:  # Snowflake unreachable: fall back to the local CSVs.
            self.connection_error = f"{type(error).__name__}: {error}"
            self.is_connected = False
            try:
                super().load_all()
            except FileNotFoundError as missing:  # Deployed bundle ships no CSVs; surface the real cause.
                raise RuntimeError(f"Snowflake unavailable ({self.connection_error}) and {missing}") from error

    def _optional(self, sql: str) -> Optional[pd.DataFrame]:
        """Outputs of the Snowflake ML functions are optional: a missing table disables that panel only."""
        try:
            return self.query(sql)
        except Exception:
            return None

    def _load_ml_function_outputs(self) -> None:
        self.anomalies = self._optional(
            "SELECT account_id, month, measure, observed, expected, lower_bound, upper_bound, is_anomaly, story "
            "FROM ML.ACCOUNT_MONTH_ANOMALIES")
        self.balance_forecast = self._optional(
            "SELECT account_id, month, forecast, lower_bound, upper_bound FROM ML.ACCOUNT_BALANCE_FORECAST")
        self.forecast_backtest = self._optional("SELECT * FROM ML.FORECAST_BACKTEST_METRICS ORDER BY horizon")
        self.vulnerability_drivers = self._optional(
            "SELECT * FROM ML.EI55_VULNERABILITY_DRIVERS ORDER BY contribution DESC")

    @property
    def forecast_validated(self) -> bool:
        """The forecast is shown only if, on average over 6 months, it beats both baselines in the 2025 backtest."""
        bt = self.forecast_backtest
        if bt is None or bt.empty:
            return False
        return bool(bt["mae_forecast"].mean() < bt["mae_naive"].mean()
                    and bt["mae_forecast"].mean() < bt["mae_constant_gap"].mean())

    def tier_track_record(self, tier: Optional[str]) -> Optional[str]:
        """What happened in the 2025 out-of-time test to account-months ranked like this tier (precision by band)."""
        m = self.model_metrics
        if m is None or m.empty or not tier:
            return None
        row = m[m["model_name"] == "XGBoost (calibrated)"]
        if row.empty:
            return None
        r = row.iloc[0]
        n = float(r["sample_count"])
        tp2, tp5 = r["precision_at_2pct"] * 0.02 * n, r["precision_at_5pct"] * 0.05 * n
        if tier.startswith("Priority"):
            rate = r["precision_at_2pct"]
            band = "top 2%"
        elif tier.startswith("Watch"):
            rate = (tp5 - tp2) / (0.03 * n)
            band = "next 3% (2-5%)"
        else:
            rate = (r["positive_count"] - tp5) / (0.95 * n)
            band = "remaining 95%"
        return f"In the 2025 test, {rate * 100:.1f}% of account-months scored in the {band} had a negative-balance day within 3 months."

    def account_anomalies(self, account_id: int) -> pd.DataFrame:
        if self.anomalies is None:
            return pd.DataFrame()
        return self.anomalies[self.anomalies["account_id"] == account_id].sort_values(["month", "measure"])

    def account_forecast(self, account_id: int) -> pd.DataFrame:
        if self.balance_forecast is None:
            return pd.DataFrame()
        return self.balance_forecast[self.balance_forecast["account_id"] == account_id].sort_values("month")

    def generate_case_narrative(self, facts: Dict[str, Any]) -> Dict[str, Any]:
        """Structured AI_COMPLETE over verified facts, then a check that every number traces back to the facts."""
        from src.services.case_narrative import NARRATIVE_SCHEMA, build_prompt, verify_numbers

        raw = self._scalar(
            "SELECT AI_COMPLETE(model => 'claude-sonnet-4-5', prompt => %s, response_format => PARSE_JSON(%s), "
            "model_parameters => {'temperature': 0})",
            (build_prompt(facts), json.dumps(NARRATIVE_SCHEMA)),
        )
        story = json.loads(raw) if isinstance(raw, str) else raw
        texts = [story.get("headline", ""), story.get("conversation_opener", ""), story.get("limits", "")]
        texts += [st.get("text", "") for st in story.get("statements", [])]
        story["unverified_numbers"] = verify_numbers(texts, facts)
        return story

    def ask_plan_coach(self, facts: Dict[str, Any], question: str,
                       history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """TANG plan coach: structured AI_COMPLETE over the on-screen plan facts, every number then checked."""
        from src.services.case_narrative import COACH_SCHEMA, build_coach_prompt, verify_numbers

        if not self.is_connected:
            return {"answer": "TANG needs the Snowflake connection; the app is running on local CSVs.",
                    "points": [], "next_step": "", "unverified_numbers": [], "error": True}
        raw = self._scalar(
            "SELECT AI_COMPLETE(model => 'claude-sonnet-4-5', prompt => %s, response_format => PARSE_JSON(%s), "
            "model_parameters => {'temperature': 0})",
            (build_coach_prompt(facts, question, history or []), json.dumps(COACH_SCHEMA)),
        )
        reply = json.loads(raw) if isinstance(raw, str) else raw
        texts = [reply.get("answer", ""), reply.get("next_step", "")] + [p.get("text", "") for p in reply.get("points", [])]
        reply["unverified_numbers"] = verify_numbers(texts, facts)
        return reply

    @property
    def source_label(self) -> str:
        return f"Snowflake · {SNOWFLAKE_DATABASE}" if self.is_connected else "Local CSV fallback"

    # ------------------------------------------------------------------ account views
    def get_transactions(self, account_id: int) -> pd.DataFrame:
        if not self.is_connected:
            return super().get_transactions(account_id)
        return self.query(
            "SELECT transaction_id, account_id, TO_VARCHAR(date) AS date, direction, operation, purpose, amount, "
            "signed_amount, balance, partner_bank, partner_account FROM RAW.TRANSACTIONS_RAW "
            "WHERE account_id = %s ORDER BY date, transaction_id",
            (int(account_id),),
        )

    def get_account_meta(self, account_id: int) -> Optional[Dict[str, Any]]:
        meta = super().get_account_meta(account_id)
        if meta is None:
            return None
        meta["statement_frequency"] = meta.get("frequency")
        if self.stress_scores is not None and account_id in self.stress_scores.index:
            row = self.stress_scores.loc[account_id]
            meta["ml_stress_probability"] = float(row["stress_probability"])
            meta["ml_risk_tier"] = row["risk_tier"]
            meta["ml_primary_risk_driver"] = row["primary_risk_driver"]
            meta["ml_as_of_month"] = row["as_of_month"]
            meta["ml_top_drivers"] = json.loads(row["top_drivers"] or "[]")
        return meta

    # ------------------------------------------------------------------ Snowflake-only services
    def run_shock_simulation(self, account_id: int, income_multiplier: float = 1.0, bills_pct: float = 0.0,
                             one_off_spend_mult: float = 0.0, one_off_fixed: float = 0.0,
                             target_months: float = 6.0) -> Optional[Dict[str, Any]]:
        """Run the deterministic SQL shock function the agent also uses."""
        if not self.is_connected:
            return None
        raw = self._scalar(
            "SELECT MART.FN_ACCOUNT_SHOCK(%s, %s, %s, %s, %s, %s)",
            (int(account_id), float(income_multiplier), float(bills_pct), float(one_off_spend_mult),
             float(one_off_fixed), float(target_months)),
        )
        return json.loads(raw) if isinstance(raw, str) else raw

    def ask_agent(self, messages: List[Dict[str, str]], account_id: Optional[int] = None) -> Dict[str, Any]:
        """Send the conversation to the Cortex Agent; return answer text plus tool provenance."""
        if not self.is_connected:
            return {"text": "The Cortex Agent needs a Snowflake connection; the app is running on local CSVs.",
                    "tools": [], "sql": [], "error": True}
        payload = []
        for i, msg in enumerate(messages):
            text = msg["content"]
            if account_id is not None and msg["role"] == "user" and i == len(messages) - 1:
                text = f"[Active account: {int(account_id)}] {text}"
            payload.append({"role": msg["role"], "content": [{"type": "text", "text": text}]})
        raw = self._scalar(f"SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN('{AGENT_NAME}', %s)",
                           (json.dumps({"messages": payload}),))
        data = json.loads(raw)
        if "content" not in data:
            return {"text": f"Agent error: {data.get('message', data)}", "tools": [], "sql": [], "error": True}
        tools, sql = [], []
        for item in data["content"]:
            if item.get("type") == "tool_use":
                use = item["tool_use"]
                tools.append({"name": use.get("name"), "input": use.get("input")})
                if use.get("input", {}).get("sql"):
                    sql.append(use["input"]["sql"])
        text = "\n".join(i["text"] for i in data["content"] if i.get("type") == "text").strip()
        return {"text": text or "(The agent returned no text.)", "tools": tools, "sql": sql, "error": False}

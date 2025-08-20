import pandas as pd
import streamlit as st
import requests
from typing import Optional

st.set_page_config(page_title="PDFlex", page_icon="📄", layout="centered")

# --- Nastavenia ---
st.sidebar.header("Nastavenia")
backend_url = st.sidebar.text_input("Backend URL", value=st.session_state.get("backend_url", "http://127.0.0.1:8001"))
if backend_url != st.session_state.get("backend_url"):
    st.session_state["backend_url"] = backend_url

# --- Pomocné funkcie ---
def api_post(path: str, json: dict, token: Optional[str] = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.post(f"{backend_url}{path}", json=json, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

def api_get(path: str, token: Optional[str] = None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(f"{backend_url}{path}", headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

# --- Login stav ---
if "token" not in st.session_state:
    st.session_state["token"] = None
if "user" not in st.session_state:
    st.session_state["user"] = None

st.title("📄 PDFlex — dashboard")

# Health check
col1, col2 = st.columns(2)
with col1:
    if st.button("🔌 Otestuj pripojenie"):
        try:
            ok = api_get("/health")
            st.success(f"Backend OK: {ok}")
        except Exception as e:
            st.error(f"Health zlyhal: {e}")

# --- Login box / profil ---
if st.session_state["token"] is None:
    st.subheader("🔑 Prihlásenie")
    with st.form("login_form"):
        email = st.text_input("E-mail", value="user@example.com")
        password = st.text_input("Heslo", type="password")
        submit = st.form_submit_button("Prihlásiť")

    if submit:
        try:
            data = api_post("/login", {"email": email, "password": password})
            st.session_state["token"] = data["access_token"]
            # načítaj profil
            me = api_get("/me", token=st.session_state["token"])
            st.session_state["user"] = me
            st.success("Prihlásenie úspešné ✅")
        except Exception as e:
            st.error(f"Login zlyhal: {e}")
else:
    st.success(f"Prihlásený: {st.session_state['user']['email']} (plan: {st.session_state['user']['plan']})")
    if st.button("Odhlásiť"):
        st.session_state["token"] = None
        st.session_state["user"] = None
        st.experimental_rerun()

# --- Keď je user prihlásený, ukáž mini náhľad API volaní ---
if st.session_state["token"]:
    st.divider()
    st.subheader("Rýchly náhľad")
    colA, colB = st.columns(2)
    with colA:
        if st.button("📃 Zoznam dokumentov"):
            try:
                docs = api_get("/documents/", token=st.session_state["token"])
                if not docs:
                    st.info("Žiadne dokumenty zatiaľ.")
                else:
                    for d in docs:
                        st.write(f"• #{d['id']} — {d['original_filename']} ({d['pages']} str.) — {d['status']}")
            except Exception as e:
                st.error(f"Chyba pri načítaní dokumentov: {e}")
    with colB:
        if st.button("ℹ️ Môj profil"):
            try:
                me = api_get("/me", token=st.session_state["token"])
                st.json(me)
            except Exception as e:
                st.error(f"Chyba pri načítaní profilu: {e}")

st.caption("Tip: Backend musí bežať na zadanom URL. Predvolené: http://127.0.0.1:8001")

# --- Upload PDF (len keď je user prihlásený) ---
if st.session_state.get("token"):
    st.divider()
    st.subheader("📤 Nahrať PDF")

    uploaded = st.file_uploader("Vyber PDF", type=["pdf"])
    if uploaded is not None:
        st.write(f"Vybrané: **{uploaded.name}**")
        if st.button("Nas?hrať na server", disabled=st.session_state.get("disabled_actions", False), help="Vyčerpaný limit"):
            try:
                files = {
                    "file": (uploaded.name, uploaded.getvalue(), "application/pdf")
                }
                headers = {"Authorization": f"Bearer {st.session_state['token']}"}
                r = requests.post(f"{backend_url}/upload", files=files, headers=headers, timeout=120)
                r.raise_for_status()
                resp = r.json()
                st.success("Nahrané ✅")
                st.json(resp)

                # Rýchly refresh zoznamu dokumentov
                try:
                    docs = api_get("/documents/", token=st.session_state["token"])
                    if docs:
                        st.write("**Moje dokumenty:**")
                        for d in docs:
                            st.write(f"• #{d['id']} — {d['original_filename']} ({d['pages']} str.) — {d['status']}")
                except Exception as e:
                    st.warning(f"Nepodarilo sa načítať zoznam dokumentov: {e}")

            except Exception as e:
                st.error(f"Upload zlyhal: {e}")

# --- pomocná DELETE ---
def api_delete(path: str, token: str):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.delete(f"{backend_url}{path}", headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()

# --- sekcia: Moje dokumenty s akciami ---
if st.session_state.get("token"):
    st.divider()
    st.subheader("📚 Moje dokumenty")

    if st.button("🔄 Obnoviť zoznam"):
        st.session_state["docs_cache"] = None

    # načítaj / cache
    docs = st.session_state.get("docs_cache")
    if docs is None:
        try:
            docs = api_get("/documents/", token=st.session_state["token"])
            st.session_state["docs_cache"] = docs
        except Exception as e:
            st.error(f"Načítanie zlyhalo: {e}")
            docs = []

    if not docs:
        st.info("Zatiaľ žiadne dokumenty.")
    else:
        for d in docs:
            with st.container(border=True):
                st.markdown(f"**#{d['id']} — {d['original_filename']}**  \n{d['pages']} strán • stav: `{d['status']}`")

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    # link na backend download
                    st.link_button("⬇️ Stiahnuť", f"{backend_url}/documents/{d['id']}/download")
                with c2:
                    st.link_button("🔐 Stiahnuť (protected)", f"{backend_url}/documents/{d['id']}/download-protected")
                with c3:
                    if st.button("📊 Štatistiky", key=f"stats_{d['id']}", disabled=st.session_state.get("disabled_actions", False), help="Vyčerpaný limit"):
                        try:
                            info = api_get(f"/documents/{d['id']}/text", token=st.session_state["token"])
                            with st.expander("Zobraziť štatistiky", expanded=True):
                                st.json(info)
                        except Exception as e:
                            st.error(f"Štatistiky zlyhali: {e}")
                with c4:
                    if st.button("🗑️ Zmazať", key=f"del_{d['id']}"):
                        try:
                            resp = api_delete(f"/documents/{d['id']}", token=st.session_state["token"])
                            st.success(f"Zmazané: #{resp.get('deleted_id')}")
                            # refresh cache
                            st.session_state["docs_cache"] = None
                            st.experimental_rerun()
                        except Exception as e:
                            st.error(f"Zmazanie zlyhalo: {e}")

# --- sekcia: 🔐 Chrániť PDF heslom ---
if st.session_state.get("token"):
    st.divider()
    st.subheader("🔐 Chrániť PDF heslom")

    try:
        docs_for_protect = api_get("/documents/", token=st.session_state["token"])
    except Exception as e:
        docs_for_protect = []
        st.error(f"Nepodarilo sa načítať dokumenty: {e}")

    if not docs_for_protect:
        st.info("Žiadne dokumenty na ochranu.")
    else:
        for d in docs_for_protect:
            with st.container(border=True):
                st.markdown(f"**#{d['id']} — {d['original_filename']}**  \n{d['pages']} strán • stav: `{d['status']}`")
                colp1, colp2, colp3 = st.columns([2,1,1])
                with colp1:
                    pwd = st.text_input("Heslo", key=f"pwd_{d['id']}", type="password", help="min. 3 znaky")
                with colp2:
                    if st.button("Zaheslovať", key=f"protect_{d['id']}", disabled=st.session_state.get("disabled_actions", False), help="Vyčerpaný limit"):
                        try:
                            if not pwd or len(pwd) < 3:
                                st.warning("Zadaj minimálne 3 znaky.")
                            else:
                                resp = api_post(f"/documents/{d['id']}/protect", {"password": pwd}, token=st.session_state["token"])
                                st.success("Vytvorená chránená kópia ✅")
                                st.json(resp)
                        except Exception as e:
                            st.error(f"Chyba pri vytváraní chránenej kópie: {e}")
                with colp3:
                    st.link_button("⬇️ Stiahnuť (protected)", f"{backend_url}/documents/{d['id']}/download-protected")

# --- sekcia: 🧠 Analýza textu (štatistiky + graf) ---
if st.session_state.get("token"):
    st.divider()
    st.subheader("🧠 Analýza textu")

    # načítame zoznam dokumentov do selectboxu
    try:
        docs_select = api_get("/documents/", token=st.session_state["token"])
    except Exception as e:
        docs_select = []
        st.error(f"Nepodarilo sa načítať dokumenty: {e}")

    if not docs_select:
        st.info("Žiadne dokumenty na analýzu.")
    else:
        options = {f"#{d['id']} — {d['original_filename']}": d['id'] for d in docs_select}
        label = st.selectbox("Vyber dokument", list(options.keys()))
        doc_id = options[label]

        if st.button("Zobraziť analýzu", disabled=st.session_state.get("disabled_actions", False), help="Vyčerpaný limit"):
            try:
                info = api_get(f"/documents/{doc_id}/text", token=st.session_state["token"])
                st.write(f"**Strán:** {info.get('pages', '—')}")
                stats = info.get("stats", {})
                colA, colB, colC = st.columns(3)
                with colA: st.metric("Slová", stats.get("words", 0))
                with colB: st.metric("Unikátne slová", stats.get("unique_words", 0))
                with colC: st.metric("Znakov", stats.get("chars", 0))

                # náhľad textu
                with st.expander("Náhľad textu (max 2000 znakov)", expanded=False):
                    st.write(info.get("text_preview", "") or "—")

                # graf TOP slov<
                top_words = stats.get("top_words", [])
                if top_words:
                    words = [w for w, _ in top_words]
                    counts = [c for _, c in top_words]
                    df = pd.DataFrame({"frekvencia": counts}, index=words)
                    st.bar_chart(df)  # index (slová) sa použije ako x-os
                else:
                    st.info("Nenašli sa žiadne top slová (možno je dokument veľmi krátky).")
            except Exception as e:
                st.error(f"Chyba pri analýze textu: {e}")

# --- sekcia: 📝 PDF → DOCX konverzia ---
if st.session_state.get("token"):
    st.divider()
    st.subheader("📝 Konvertovať PDF → DOCX")

    import re
    def _filename_from_cd(headers, fallback: str) -> str:
        cd = headers.get("Content-Disposition", "")
        m = re.search(r'filename="?([^";]+)"?', cd)
        return m.group(1) if m else fallback

    # načítaj dokumenty do selectboxu
    try:
        docs_conv = api_get("/documents/", token=st.session_state["token"])
    except Exception as e:
        docs_conv = []
        st.error(f"Nepodarilo sa načítať dokumenty: {e}")

    if not docs_conv:
        st.info("Žiadne dokumenty na konverziu.")
    else:
        options = {f"#{d['id']} — {d['original_filename']}": d['id'] for d in docs_conv}
        label = st.selectbox("Vyber dokument", list(options.keys()), key="conv_select")
        doc_id = options[label]

        if st.button("Konvertovať na \.docx", disabled=st.session_state.get("disabled_actions", False), help="Vyčerpaný limit"):
            try:
                headers = {"Authorization": f"Bearer {st.session_state['token']}"}
                r = requests.post(f"{backend_url}/documents/{doc_id}/convert/docx", headers=headers, timeout=300)
                r.raise_for_status()
                fname = _filename_from_cd(r.headers, fallback=f"document_{doc_id}.docx")
                st.session_state["docx_bytes"] = r.content
                st.session_state["docx_name"] = fname
                st.success("Konverzia hotová ✅ nižšie si stiahni súbor.")
            except Exception as e:
                st.error(f"Konverzia zlyhala: {e}")

        # ak už máme konvertovaný obsah v session, ukáž tlačidlo na stiahnutie
        if st.session_state.get("docx_bytes"):
            st.download_button(
                "⬇️ Stiahnuť DOCX",
                data=st.session_state["docx_bytes"],
                file_name=st.session_state.get("docx_name", "document.docx"),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

# --- sekcia: 📈 Limity / Kredity ---
if st.session_state.get("token"):
    st.divider()
    st.subheader("📈 Limity / Kredity")

    colL, colR = st.columns([1,1])
    with colL:
        if st.button("🔄 Obnoviť limity"):
            st.session_state.pop("usage_cache", None)

    try:
        usage = st.session_state.get("usage_cache")
        if usage is None:
            # používame náš backend endpoint
            usage = api_get("/usage/me", token=st.session_state["token"])
            st.session_state["usage_cache"] = usage

        used = int(usage.get("used_this_month", usage.get("used", 0)))
        limit = int(usage.get("limit", 20))
        remaining = int(usage.get("remaining", max(0, limit - used)))
        pct = int(100 * used / limit) if limit > 0 else 0

        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Použití tento mesiac", used)
        with c2: st.metric("Limit", limit)
        with c3: st.metric("Zostáva", remaining)

        st.progress(min(max(pct, 0), 100), text=f"Využitie {pct}%")

        # rozpis podľa akcie (ak backend poslal)
        by_action = usage.get("by_action", {})
        if by_action:
            with st.expander("Rozpis podľa akcií", expanded=False):
                for k, v in by_action.items():
                    st.write(f"• **{k}**: {v}")

        st.caption(f"Účtovacie obdobie od {usage.get('month_start_utc','—')}")
    except Exception as e:
        st.error(f"Nepodarilo sa načítať limity: {e}")

# --- helpers: usage/credits cache + prepínač disabled_actions ---
def _get_usage_cached():
    if "usage_cache" not in st.session_state:
        try:
            st.session_state["usage_cache"] = api_get("/usage/me", token=st.session_state.get("token"))
        except Exception:
            st.session_state["usage_cache"] = {"used_this_month": 0, "limit": 20, "remaining": 20}
    return st.session_state["usage_cache"]

def can_use_actions():
    usage = _get_usage_cached()
    used = int(usage.get("used_this_month", usage.get("used", 0)))
    limit = int(usage.get("limit", 20))
    remaining = int(usage.get("remaining", max(0, limit - used)))
    return remaining > 0

# globálny prepínač pre tlačidlá, ktoré míňajú kredit
st.session_state["disabled_actions"] = not can_use_actions()

# --- Globálne upozornenie pri vyčerpaní limitu ---
if st.session_state.get("token") and st.session_state.get("disabled_actions"):
    st.warning("❗ Vyčerpaný limit bezplatného plánu. Akcie sú dočasne vypnuté.")

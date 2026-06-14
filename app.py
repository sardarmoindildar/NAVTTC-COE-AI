import streamlit as st
import streamlit.components.v1 as components
import edge_tts
import asyncio
import tempfile
import os
import time
import threading
import base64
import io
import speech_recognition as sr
from streamlit_mic_recorder import mic_recorder

# ============================================
# PAGE CONFIGURATION
# ============================================
st.set_page_config(
    page_title="NAVTTC Receptionist",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================
# SAFE CUSTOM CSS FOR BUTTON BOUNDARIES & CHAT UI
# ============================================
st.markdown("""
<style>
div.stButton > button {
    border: 1px solid #777777 !important;
    border-radius: 8px !important;
    box-shadow: 0px 2px 4px rgba(0,0,0,0.2) !important;
    transition: all 0.3s ease;
}
div.stButton > button:hover {
    border-color: #ff4b4b !important;
    box-shadow: 0px 4px 8px rgba(255,75,75,0.4) !important;
}

/* Hide the default mic visually until Javascript locks it into place to avoid flickering */
div.element-container:has(iframe[title*="mic_recorder"]) {
    opacity: 0;
    transition: opacity 0.3s ease-in;
}

iframe[title*="mic_recorder"] {
    background: transparent !important;
    border: none !important;
}

/* Base styling for the text area */
div[data-testid="stChatInput"] > div {
    border-radius: 24px !important;
    background-color: #f0f4f9 !important;
    border: none !important;
    padding-right: 60px !important;
}

div[data-testid="stChatInput"] textarea {
    background-color: transparent !important;
}
</style>
""", unsafe_allow_html=True)

# ============================================
# SESSION STATE
# ============================================
if "language" not in st.session_state:
    st.session_state.language = "English"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_query" not in st.session_state:
    st.session_state.last_query = ""
if "audio_html" not in st.session_state:
    st.session_state.audio_html = ""
if "menu_level" not in st.session_state:
    st.session_state.menu_level = "main"

# ============================================
# VOICE FUNCTIONS 
# ============================================
def generate_audio_bytes(text, lang_code):
    try:
        formatted_text = text.replace("|", ". ").replace("...", ".").replace("*", "").replace("#", "") 
        voice = "ur-IN-GulNeural" if lang_code == "ur" else "en-GB-SoniaNeural"

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            filename = fp.name
            
        async def _generate():
            communicate = edge_tts.Communicate(formatted_text, voice, rate="-5%", pitch="+2Hz")
            await communicate.save(filename)
            
        asyncio.run(_generate())

        with open(filename, "rb") as f:
            audio_bytes = f.read()
        
        def remove_file():
            time.sleep(3) 
            try:
                os.unlink(filename)
            except:
                pass
        threading.Thread(target=remove_file).start()
        return audio_bytes
    except Exception as e:
        print(f"Voice error: {e}")
        return None

def set_audio_html(audio_bytes):
    if audio_bytes:
        b64 = base64.b64encode(audio_bytes).decode()
        unique_id = f"audio_{int(time.time() * 1000)}"
        
        audio_tag = f"""
            <script>
                var old_audios = window.parent.document.getElementsByTagName('audio');
                for (var i = 0; i < old_audios.length; i++) {{
                    old_audios[i].pause();
                    old_audios[i].removeAttribute('src');
                }}
            </script>
            <audio autoplay="true" id="{unique_id}" onended="window.parent.document.querySelectorAll('button').forEach(btn => {{ if(btn.innerText.includes('Stop Audio') || btn.innerText.includes('آواز روکیں')) btn.click(); }})">
                <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            <script>
                setTimeout(function() {{
                    var newAudio = window.parent.document.getElementById('{unique_id}');
                    if(newAudio) {{
                        var playPromise = newAudio.play();
                        if (playPromise !== undefined) {{
                            playPromise.catch(function(error) {{ console.log("Force playing."); }});
                        }}
                    }}
                }}, 50);
            </script>
            """
        st.session_state.audio_html = audio_tag

# ============================================
# COURSE & PROGRAM DATABASE 
# ============================================
COURSES_EN = {
    "ai robotics": {"name": "AI (Robotics)", "duration": "3 Months", "entry": "Bachelor in IT/CS/Maths/Engineering"},
    "e-commerce": {"name": "E-Commerce", "duration": "3 Months", "entry": "Intermediate"},
    "digital marketing": {"name": "Digital Marketing & SEO", "duration": "3 Months", "entry": "Intermediate"},
    "welding": {"name": "Advanced Welding", "duration": "6 Months", "entry": "Matric / DAE Mechanical"},
    "fashion": {"name": "Fashion Designing", "duration": "6 Months", "entry": "Matric (SSC)"},
    "cnc": {"name": "Advance CNC Operator", "duration": "6 Months", "entry": "Matric / DAE Mechanical"},
    "electrical": {"name": "Electrical Power System", "duration": "6 Months", "entry": "DAE Electrical/Electronics"}
}

COURSES_UR = {
    "ai robotics": {"name": "اے آئی (روبوٹکس)", "duration": "3 ماہ", "entry": "بیچلر ان آئی ٹی/کمپیوٹر سائنس"},
    "e-commerce": {"name": "ای کامرس", "duration": "3 ماہ", "entry": "انٹرمیڈیٹ"},
    "digital marketing": {"name": "ڈیجیٹل مارکیٹنگ", "duration": "3 ماہ", "entry": "انٹرمیڈیٹ"},
    "welding": {"name": "ایڈوانسڈ ویلڈنگ", "duration": "6 ماہ", "entry": "میٹرک / ڈی اے ای مکینیکل"},
    "fashion": {"name": "فیشن ڈیزائننگ", "duration": "6 ماہ", "entry": "میٹرک (ایس ایس سی)"},
    "cnc": {"name": "سی این سی آپریٹر", "duration": "6 ماہ", "entry": "میٹرک / ڈی اے ای مکینیکل"},
    "electrical": {"name": "الیکٹریکل پاور سسٹم", "duration": "6 ماہ", "entry": "ڈی اے ای الیکٹریکل"}
}

def get_response(query, lang):
    q = query.lower()
    
    if q == "stop_audio_command":
        return "Audio stopped." if lang == "English" else "آواز روک دی گئی ہے۔"
        
    if "ogdcl" in q:
        if lang == "English":
            return "### OGDCL-CSR Program\n* **Stipend:** 5,000 PKR\n* **Allowance:** 7,500 PKR Travelling\n* **Facilities:** Hostel & 3 meals a day\n* **Activities:** Islamabad Tour & Industrial Visit"
        else:
            return "### او جی ڈی سی ایل پروگرام\n* **وظیفہ:** 5000 روپے\n* **الاؤنس:** 7500 روپے سفری الاؤنس\n* **سہولیات:** ہاسٹل اور 3 وقت کا کھانا\n* **سرگرمیاں:** اسلام آباد کا دورہ اور انڈسٹریل وزٹ"
            
    if "pmydp" in q or "regular program" in q:
        return "The Regular Program (PMYDP) offers completely Free Courses." if lang == "English" else "ریگولر پروگرام (PMYDP) میں تمام کورسز بالکل مفت ہیں۔"
    if "contact" in q or "رابطہ" in q:
        return "Contact our Helpline at: 051-111-628-882" if lang == "English" else "ہماری ہیلپ لائن پر رابطہ کریں: 882-628-111-051"
    if "admission" in q or "داخلہ" in q:
        return "For admission, visit the nearest NAVTTC center or www.navttc.gov.pk" if lang == "English" else "داخلے کے لیے قریبی NAVTTC مرکز یا www.navttc.gov.pk ملاحظہ کریں۔"

    courses = COURSES_EN if lang == "English" else COURSES_UR
    for key, data in courses.items():
        if key in q or data["name"].lower() in q:
            if lang == "English":
                return f"### {data['name']}\n* **Duration:** {data['duration']}\n* **Eligibility:** {data['entry']}\n* **Cost:** Free\n* **Perks:** Industrial Visit included."
            else:
                return f"### {data['name']}\n* **دورانیہ:** {data['duration']}\n* **اہلیت:** {data['entry']}\n* **فیس:** مفت\n* **خصوصیات:** انڈسٹریل وزٹ شامل ہے۔"
                
    return "Please ask about a specific course or program." if lang == "English" else "براہ کرم کسی مخصوص کورس یا پروگرام کے بارے میں پوچھیں۔"

# ============================================
# CALLBACK FOR SPEECH PROCESSING
# ============================================
def voice_callback():
    if "my_recorder" in st.session_state and st.session_state.my_recorder:
        # INSTANTLY kill old audio when mic finishes recording
        st.session_state.audio_html = "" 
        audio_bytes = st.session_state.my_recorder['bytes']
        try:
            r = sr.Recognizer()
            audio_file = io.BytesIO(audio_bytes)
            with sr.AudioFile(audio_file) as source:
                audio = r.record(source)
            lang_tag = "en-US" if st.session_state.language == "English" else "ur-PK"
            text = r.recognize_google(audio, language=lang_tag)
            
            if text.lower().strip() in ["stop", "stop speaking", "رکیں", "چپ کرو"]:
                st.session_state.last_query = "stop_audio_command"
            else:
                st.session_state.last_query = text
        except Exception as e:
            print("Speech recognition error:", e)

# ============================================
# UI HEADER
# ============================================
spacer_left, col_logo, col_title, spacer_right = st.columns([2, 1, 5, 2])

with col_logo:
    try:
        st.image("logo.png", width=100)
    except FileNotFoundError:
        st.error("Image not found. Make sure it is named logo.png")

with col_title:
    st.markdown("<h1 style='color: #198754; margin-top: 5px; white-space: nowrap;'>NAVTTC Receptionist</h1>", unsafe_allow_html=True)

col_lang1, col_lang2, col_mic = st.columns([1, 1, 4]) 
with col_lang1:
    if st.button("English", use_container_width=True):
        st.session_state.audio_html = "" # Instantly kill old audio on language change
        st.session_state.language = "English"
        st.rerun()
with col_lang2:
    if st.button("اردو", use_container_width=True):
        st.session_state.audio_html = "" # Instantly kill old audio on language change
        st.session_state.language = "Urdu"
        st.rerun()

st.markdown("---")
# ============================================
# HIERARCHICAL MENU BUTTONS
# ============================================
def make_menu_row(buttons):
    cols = st.columns(len(buttons))
    for i, (label, query, menu_action) in enumerate(buttons):
        if cols[i].button(label, use_container_width=True):
            # THE FIX: Instantly kill old audio the millisecond any menu button is clicked
            st.session_state.audio_html = "" 
            if menu_action:
                st.session_state.menu_level = menu_action
            if query:
                st.session_state.last_query = query
            st.rerun()

if st.session_state.menu_level == "main":
    if st.session_state.language == "English":
        make_menu_row([("📂 Programs", None, "programs"), ("📞 Contact", "contact", None), ("🎓 Admission", "admission", None)])
    else:
        make_menu_row([("📂 پروگرامز", None, "programs"), ("📞 رابطہ", "contact", None), ("🎓 داخلہ", "admission", None)])

elif st.session_state.menu_level == "programs":
    if st.session_state.language == "English":
        make_menu_row([("⬅️ Back", None, "main"), ("🏢 OGDCL-CSR", "ogdcl", None), ("📘 Regular (PMYDP)", None, "courses")])
    else:
        make_menu_row([("⬅️ پیچھے", None, "main"), ("🏢 او جی ڈی سی ایل", "ogdcl", None), ("📘 ریگولر پروگرام", None, "courses")])

elif st.session_state.menu_level == "courses":
    if st.session_state.language == "English":
        make_menu_row([("⬅️ Back to Programs", None, "programs"), ("🤖 AI Robotics", "ai robotics", None), ("🛒 E-Commerce", "e-commerce", None)])
        make_menu_row([("🔧 Welding", "welding", None), ("👗 Fashion", "fashion", None), ("⚙️ CNC", "cnc", None)])
    else:
        make_menu_row([("⬅️ پیچھے", None, "programs"), ("🤖 اے آئی روبوٹکس", "ai robotics", None), ("🛒 ای کامرس", "e-commerce", None)])
        make_menu_row([("🔧 ویلڈنگ", "welding", None), ("👗 فیشن", "fashion", None), ("⚙️ سی این سی", "cnc", None)])

st.markdown("---")

# ============================================
# STOP AUDIO BUTTON
# ============================================
if st.session_state.audio_html:
    col_stop1, col_stop2 = st.columns([1, 4])
    with col_stop1:
        if st.button("⏹️ Stop Audio" if st.session_state.language == "English" else "⏹️ آواز روکیں", use_container_width=True):
            st.session_state.audio_html = "" 
            st.rerun()
    with col_stop2:
        st.markdown(st.session_state.audio_html, unsafe_allow_html=True)

# ============================================
# CHAT INTERFACE & INPUT BOX
# ============================================
for msg in st.session_state.messages:
    if msg["content"] != "stop_audio_command": 
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# Text Input Box
user_typed_input = st.chat_input("Ask me something" if st.session_state.language == "English" else "سوال پوچھیں...")

if user_typed_input:
    # Instantly kill old audio if they type something manually
    st.session_state.audio_html = "" 
    st.session_state.last_query = user_typed_input
    st.rerun()

# Mic Input Box
mic_recorder(
    start_prompt="🎙️", 
    stop_prompt="🛑", 
    key="my_recorder",
    format="wav",
    callback=voice_callback
)

# ============================================
# SAFE JAVASCRIPT HACK (FLOATS THE MIC OVER THE BAR)
# ============================================
components.html("""
<script>
const doc = window.parent.document;
function morphToGemini() {
    const chatInputContainer = doc.querySelector('[data-testid="stChatInput"]');
    const micIframe = doc.querySelector('iframe[title*="mic_recorder"]');
    
    if (chatInputContainer && micIframe) {
        const micContainer = micIframe.closest('.element-container');
        const innerBox = chatInputContainer.querySelector('div'); 
        
        if (micContainer && innerBox) {
            const boxRect = innerBox.getBoundingClientRect();
            micContainer.style.position = 'fixed';
            micContainer.style.left = (boxRect.right - 55) + 'px'; 
            micContainer.style.top = (boxRect.top + (boxRect.height / 2) - 17) + 'px'; 
            micContainer.style.zIndex = '999999';
            micContainer.style.width = '35px';
            micContainer.style.height = '35px';
            micContainer.style.opacity = '1';
            micContainer.style.background = 'transparent';
            micContainer.style.backgroundColor = 'transparent';

            try {
                const iframeDoc = micIframe.contentDocument || micIframe.contentWindow.document;
                if (iframeDoc) {
                    iframeDoc.body.style.background = 'transparent';
                    iframeDoc.body.style.backgroundColor = 'transparent';
                    const btn = iframeDoc.querySelector('button');
                    if (btn && !btn.dataset.modified) {
                        btn.innerHTML = `<svg viewBox="0 0 24 24" width="22" height="22" fill="#444746"><path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5-3c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/></svg>`;
                        btn.style.background = 'transparent';
                        btn.style.backgroundColor = 'transparent';
                        btn.style.border = 'none';
                        btn.style.boxShadow = 'none';
                        btn.style.padding = '0px';
                        btn.style.cursor = 'pointer';
                        btn.dataset.modified = "true";
                    }
                }
            } catch(e) {}
        }
    }
}
setInterval(morphToGemini, 10); 

doc.addEventListener('keydown', function(e) {
    if(e.key === 'Enter') {
        const audios = doc.querySelectorAll('audio');
        audios.forEach(audio => {
            audio.pause();
            audio.removeAttribute('src'); 
        });
    }
});
</script>
""", height=0)

# ============================================
# FINAL EXECUTION: PROCESS THE QUERY & GENERATE VOICE
# ============================================
if st.session_state.last_query:
    query_text = st.session_state.last_query
    st.session_state.last_query = "" # Clear it so it doesn't loop
    
    st.session_state.messages.append({"role": "user", "content": query_text})
    if query_text != "stop_audio_command":
        with st.chat_message("user"):
            st.markdown(query_text)

    response = get_response(query_text, st.session_state.language)
    lang_code = "en" if st.session_state.language == "English" else "ur"
    
    # Generate the new voice (This takes 2 to 3 seconds)
    audio_bytes = generate_audio_bytes(response, lang_code)
    set_audio_html(audio_bytes)
    
    st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Rerun one last time to instantly show the new voice player
    st.rerun() 

if not st.session_state.messages:
    msg = "👋 Welcome! Click the mic to ask." if st.session_state.language == "English" else "👋 خوش آمدید! بول کر پوچھنے کے لیے مائیک پر کلک کریں۔"
    st.info(msg)
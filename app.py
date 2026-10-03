import base64
import html
import io
import os
import time

import streamlit as st
from gtts import gTTS
from huggingface_hub import InferenceClient
from PIL import Image, ImageOps


DEFAULT_MODELS = [
    "Qwen/Qwen2.5-VL-7B-Instruct",
    "Qwen/Qwen2.5-VL-32B-Instruct",
    "google/gemma-3-27b-it",
    "meta-llama/Llama-4-Scout-17B-16E-Instruct",
]

SYSTEM_PROMPT = (
    "أنت «عين»، مساعد لشخص كفيف أو ضعيف البصر. هو لا يرى الصورة، وسيسمع ردك بصوت عالي. "
    "تكلم بالعربية الفصحى المبسطة، بجمل قصيرة وواضحة، بدون رموز أو نجوم أو قوائم مرقمة أو إيموجي. "
    "ابدأ بأهم معلومة مباشرة. اذكر أي خطر أو عائق بوضوح في البداية (درج، سيارة، حافة، نار، زجاج مكسور). "
    "استخدم اتجاهات مفيدة مثل: أمامك، على يمينك، على يسارك، قريب، بعيد. "
    "لا تخترع تفاصيل غير موجودة. إذا كانت الصورة غير واضحة أو مظلمة أو مهزوزة، قل ذلك واقترح كيف يصورها أفضل."
)

MODES = {
    "وصف المكان": (
        "صف ما أمامي في 3 إلى 5 جمل. ابدأ بأي عائق أو خطر إن وجد، "
        "ثم الأشياء الرئيسية وأماكنها بالنسبة لي، ثم أي أشخاص وما يفعلونه."
    ),
    "اقرأ الكلام": (
        "اقرأ كل النص المكتوب في الصورة كما هو حرفياً، بلغته الأصلية، وبترتيب القراءة الطبيعي. "
        "لا تشرح ولا تلخص. إذا كان النص بالإنجليزية اقرأه كما هو ثم قل ترجمته العربية في جملة واحدة. "
        "إذا لم يوجد نص قل: لا يوجد كلام مكتوب في الصورة."
    ),
    "منتج أو علبة": (
        "هذه صورة منتج أو علبة. قل لي: اسم المنتج، ونوعه، وتاريخ الانتهاء إن ظهر، "
        "والحجم أو الوزن إن ظهر، وأي تحذير مكتوب. إذا كان دواء، اقرأ الاسم والتركيز فقط كما هو مكتوب "
        "ولا تعطِ نصيحة طبية، وذكّرني بالتأكد من الصيدلي. إذا لم يظهر شيء من ذلك قل أي جزء أصوره."
    ),
    "فلوس": (
        "حدد العملات الورقية أو المعدنية في الصورة: نوعها وقيمة كل واحدة، ثم المجموع. "
        "إذا لم تكن متأكداً من قيمة ورقة قل ذلك بوضوح."
    ),
    "ألوان ولبس": (
        "صف ألوان الملابس أو الأشياء الظاهرة بدقة، وهل الألوان متناسقة مع بعض أم لا، "
        "وأي بقع أو تلف ظاهر."
    ),
}

ICONS = {
    "وصف المكان": "explore",
    "اقرأ الكلام": "article",
    "منتج أو علبة": "inventory_2",
    "فلوس": "payments",
    "ألوان ولبس": "checkroom",
}

SOURCES = {"الكاميرا": "photo_camera", "رفع صورة": "upload"}

FONT_SIZES = {"عادي": 18, "كبير": 21, "كبير جداً": 24}
FONT_SIZE_PARAMS = {"عادي": "normal", "كبير": "large", "كبير جداً": "xlarge"}


st.set_page_config(page_title="عين", page_icon="👁️", layout="centered", initial_sidebar_state="collapsed")

CSS = """
<style>
:root {
  --bg: #FFFFFF;
  --surface: #F7F8FA;
  --ink: #111827;
  --muted: #6B7280;
  --line: #E5E7EB;
  --line-strong: #D1D5DB;
  --primary: #2563EB;
  --primary-press: #1D4ED8;
  --primary-soft: #EFF6FF;
  --success: #059669;
  --success-ink: #047857;
  --danger: #DC2626;
  --danger-ink: #B91C1C;
  --danger-soft: #FEF2F2;
  --r-sm: 12px;
  --r-md: 16px;
  --r-lg: 20px;
  --shadow: 0 1px 2px rgba(17, 24, 39, .04), 0 10px 30px -12px rgba(17, 24, 39, .12);
  --font: "IBM Plex Sans Arabic", "Segoe UI", Tahoma, Arial, sans-serif;
  color-scheme: light only;
}

html, body, .stApp { background: var(--bg) !important; color: var(--ink); }
.stApp, .stApp button, .stApp input, .stApp textarea { font-family: var(--font); }

[data-testid="stToolbarActions"], [data-testid="stAppDeployButton"], [data-testid="stMainMenu"],
[data-testid="stStatusWidget"], [data-testid="stDecoration"], #MainMenu, footer { display: none !important; }
[data-testid="stHeader"] { background: transparent !important; pointer-events: none; }
[data-testid="stHeader"] button { pointer-events: auto; }
.st-key-ain_css, .st-key-ain_js { display: none !important; }
[data-stale="true"] { opacity: 1 !important; }

[data-testid="stExpandSidebarButton"] {
  min-height: 48px; padding: 0 16px 0 12px !important; gap: 6px;
  background: var(--bg) !important; border: 1px solid var(--line) !important; border-radius: 999px !important;
  color: var(--ink) !important; box-shadow: 0 1px 2px rgba(17, 24, 39, .05);
}
[data-testid="stExpandSidebarButton"]:hover { border-color: var(--line-strong) !important; background: var(--surface) !important; }
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] { font-size: 0 !important; }
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"]::before {
  content: "tune"; font-family: "Material Symbols Rounded"; font-size: 1.375rem; color: var(--primary);
}
[data-testid="stExpandSidebarButton"]::after { content: "الإعدادات"; font-size: .9375rem; font-weight: 600; }

[data-testid="stMain"], [data-testid="stSidebarUserContent"] { direction: rtl; text-align: right; }
[data-testid="stMainBlockContainer"] { max-width: 720px; padding: 4.5rem 1.5rem 5rem; }
[data-testid="stMain"] p, [data-testid="stMain"] li { font-size: 1rem; line-height: 1.75; }

.stApp :focus-visible { outline: 3px solid var(--primary) !important; outline-offset: 3px !important; border-radius: var(--r-sm); }
.stApp button:focus { box-shadow: none; }

.ain-hero { margin: 0 0 1.25rem; }
.ain-brand { display: flex; align-items: center; gap: .875rem; }
.ain-logo {
  width: 3rem; height: 3rem; border-radius: 50%; flex: none;
  border: .1875rem solid var(--primary); background: var(--primary-soft);
  display: grid; place-items: center;
}
.ain-logo span { width: 1rem; height: 1rem; border-radius: 50%; background: var(--primary); display: block; }
.ain-title { font-size: 3.25rem; font-weight: 700; line-height: 1.1; letter-spacing: -.01em; color: var(--ink); margin: 0; padding: 0; }
.ain-tagline { font-size: 1.125rem; line-height: 1.7; color: var(--muted); margin: .875rem 0 0; max-width: 32em; }

[data-testid="stMain"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebarUserContent"] [data-testid="stWidgetLabel"] p {
  font-size: 1.125rem !important; font-weight: 600; color: var(--ink); line-height: 1.5;
}
[data-testid="stMain"] [data-testid="stWidgetLabel"] { margin-bottom: .5rem; }
.ain-section-title { font-size: 1.125rem; font-weight: 600; color: var(--ink); margin: 0; }

.st-key-modes { margin-top: .75rem; }
.st-key-modes .stElementContainer, .st-key-modes [data-testid="stRadio"] { width: 100% !important; }
.st-key-modes [role="radiogroup"] {
  display: grid !important; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: .75rem; width: 100%;
}
.st-key-modes [role="radiogroup"] > label {
  position: relative; margin: 0 !important; padding: 1.125rem .5rem 1rem; min-height: 7rem;
  display: flex; align-items: center; justify-content: center; cursor: pointer;
  background: var(--surface); border: 2px solid var(--line); border-radius: var(--r-md);
}
.st-key-modes [role="radiogroup"] > label:hover { border-color: var(--line-strong); background: #F1F3F6; }
.st-key-modes [role="radiogroup"] > label div:has([data-testid="stMarkdownContainer"]) {
  padding: 0 !important; margin: 0 !important; gap: 0 !important; width: 100%; justify-content: center;
}
.st-key-modes [role="radiogroup"] > label p {
  display: flex; flex-direction: column; align-items: center; gap: .5rem; text-align: center;
  margin: 0; font-size: 1rem !important; font-weight: 600; line-height: 1.35; color: var(--ink);
}
.st-key-modes [role="radiogroup"] > label p [role="img"] { font-size: 1.875rem; line-height: 1; color: #4B5563; }
.st-key-modes [role="radiogroup"] > label:has(input:checked) {
  border-color: var(--primary); background: var(--primary-soft);
}
.st-key-modes [role="radiogroup"] > label:has(input:checked) p [role="img"] { color: var(--primary); }
.st-key-modes [role="radiogroup"] > label:has(input:checked)::after {
  content: "check"; font-family: "Material Symbols Rounded"; font-size: 1rem; line-height: 1;
  position: absolute; top: -.5rem; left: -.5rem; width: 1.5rem; height: 1.5rem;
  display: grid; place-items: center; border-radius: 50%; background: var(--primary); color: #fff;
  box-shadow: 0 0 0 3px var(--bg);
}
.st-key-modes [role="radiogroup"] > label:has(input:focus-visible) { outline: 3px solid var(--primary); outline-offset: 3px; }

.st-key-capture {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-lg);
  padding: 1.25rem; gap: 1rem; margin-top: .5rem;
}

.st-key-src .stElementContainer, .st-key-src [data-testid="stRadio"] { width: 100% !important; }
.st-key-src [role="radiogroup"], .st-key-font_size [role="radiogroup"] {
  display: grid !important; grid-template-columns: 1fr 1fr; gap: .25rem; width: 100%;
  padding: .25rem; background: var(--bg); border: 1px solid var(--line); border-radius: 14px;
}
.st-key-font_size [role="radiogroup"] { grid-template-columns: 1fr; }
.st-key-src [role="radiogroup"] > label, .st-key-font_size [role="radiogroup"] > label {
  margin: 0 !important; min-height: 3rem; padding: .25rem .75rem; border-radius: 10px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.st-key-font_size [role="radiogroup"] > label { justify-content: flex-start; }
.st-key-src [role="radiogroup"] > label div:has([data-testid="stMarkdownContainer"]),
.st-key-font_size [role="radiogroup"] > label div:has([data-testid="stMarkdownContainer"]) {
  padding: 0 !important; margin: 0 !important; gap: 0 !important;
}
:is(.st-key-modes, .st-key-src, .st-key-font_size) [role="radiogroup"] > label
  div:not([data-testid="stMarkdownContainer"]):not(:has([data-testid="stMarkdownContainer"])):not([data-testid="stMarkdownContainer"] *) {
  display: none !important;
}
.st-key-src [role="radiogroup"] p, .st-key-font_size [role="radiogroup"] p {
  margin: 0; font-size: 1rem !important; font-weight: 600; color: var(--ink);
  display: flex; align-items: center; gap: .5rem;
}
.st-key-src [role="radiogroup"] p [role="img"] { font-size: 1.375rem; }
.st-key-src [role="radiogroup"] > label:hover, .st-key-font_size [role="radiogroup"] > label:hover { background: var(--surface); }
.st-key-src [role="radiogroup"] > label:has(input:checked),
.st-key-font_size [role="radiogroup"] > label:has(input:checked) { background: var(--primary); }
.st-key-src [role="radiogroup"] > label:has(input:checked) p,
.st-key-font_size [role="radiogroup"] > label:has(input:checked) p { color: #fff; }
.st-key-src [role="radiogroup"] > label:has(input:focus-visible),
.st-key-font_size [role="radiogroup"] > label:has(input:focus-visible) { outline: 3px solid var(--primary); outline-offset: 2px; }
.st-key-font_size [role="radiogroup"] > label:nth-child(2) p { font-size: 1.125rem !important; }
.st-key-font_size [role="radiogroup"] > label:nth-child(3) p { font-size: 1.25rem !important; }

[data-testid="stCameraInputWebcamStyledBox"], [data-testid="stCameraInput"] img, [data-testid="stCameraInput"] video {
  border-radius: var(--r-md) var(--r-md) 0 0 !important;
}
[data-testid="stCameraInputWebcamStyledBox"] { background: #EEF0F3; border: 1px solid var(--line); border-bottom: 0; }
[data-testid="stCameraInputWebcamStyledBox"] * { color: var(--ink); }
[data-testid="stCameraInputButton"] {
  min-height: 3.25rem; width: 100%; border-radius: 0 0 var(--r-md) var(--r-md) !important;
  background: var(--bg) !important; border: 1px solid var(--line) !important; color: transparent !important;
  font-size: 0 !important; display: flex !important; flex-direction: row !important;
  align-items: center; justify-content: center; gap: .5rem; padding: .5rem 1rem !important;
}
[data-testid="stCameraInputButton"]:hover { background: var(--primary-soft) !important; }
[data-testid="stCameraInputButton"]::before {
  content: "photo_camera"; font-family: "Material Symbols Rounded"; font-size: 1.5rem; color: var(--primary);
}
[data-testid="stCameraInputButton"]::after { content: "صوّر دلوقتي"; font-size: 1.0625rem; font-weight: 600; color: var(--ink); }
[data-testid="stCameraInputButton"][data-ain-state="clear"]::before { content: "restart_alt"; }
[data-testid="stCameraInputButton"][data-ain-state="clear"]::after { content: "امسح الصورة وصوّر تاني"; }

[data-testid="stFileUploaderDropzone"] {
  background: var(--bg) !important; border: 2px dashed var(--line-strong) !important; border-radius: var(--r-md) !important;
  padding: 1.5rem 1.25rem !important; min-height: 9rem; gap: 1rem;
  display: flex !important; flex-direction: column !important; align-items: center !important; justify-content: center;
}
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--primary) !important; background: var(--primary-soft) !important; }
[data-testid="stFileUploaderDropzoneInstructions"] { flex-direction: column; align-items: center; text-align: center; gap: .5rem; margin: 0 !important; }
[data-testid="stFileUploaderDropzoneInstructions"] > span { margin: 0 !important; color: var(--primary); }
[data-testid="stFileUploaderDropzoneInstructions"] > span svg { width: 2.25rem; height: 2.25rem; }
[data-testid="stFileUploaderDropzoneInstructions"] > div > span { display: none !important; }
[data-testid="stFileUploaderDropzoneInstructions"] > div::before {
  content: "اسحب الصورة وسيبها هنا"; display: block; font-size: 1rem; font-weight: 600; color: var(--ink);
}
[data-testid="stFileUploaderDropzoneInstructions"] > div::after {
  content: "JPG أو PNG أو WEBP · لحد 15 ميجا"; display: block; font-size: .875rem; color: var(--muted); margin-top: .25rem;
}
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] {
  min-height: 3rem; padding: 0 1.25rem !important; font-size: 0 !important; color: transparent !important;
  background: var(--bg) !important; border: 1.5px solid var(--line-strong) !important; border-radius: 14px !important;
}
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] { display: inline-flex !important; align-items: center; gap: .5rem; }
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] > * { display: none !important; }
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"]::before {
  content: "upload"; font-family: "Material Symbols Rounded"; font-size: 1.375rem; color: var(--primary);
}
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"]::after { content: "اختار صورة من جهازك"; font-size: 1rem; font-weight: 600; color: var(--ink); }
[data-testid="stFileUploaderFile"] { direction: rtl; }
[data-testid="stFileChipDeleteBtn"] button, [data-testid="stFileUploaderDeleteBtn"] button,
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-borderlessIcon"] { min-width: 48px; min-height: 48px; }
[data-testid="stFileChipName"] { font-size: 1rem; color: var(--ink); }
[data-testid="stFileUploaderFileName"] { font-size: 1rem; color: var(--ink); }

.st-key-question { margin-top: .75rem; }
[data-testid="stTextInputRootElement"] {
  min-height: 3.5rem; border-radius: 14px !important; border: 1.5px solid var(--line-strong) !important; background: var(--bg) !important;
}
[data-testid="stTextInputRootElement"]:focus-within { border-color: var(--primary) !important; outline: 3px solid rgba(37, 99, 235, .35); outline-offset: 1px; }
[data-testid="stTextInputRootElement"] input { font-size: 1rem !important; padding: 0 1rem !important; color: var(--ink); background: transparent !important; }
[data-testid="stTextInputRootElement"] input::placeholder { color: var(--muted); opacity: 1; }
[data-testid="InputInstructions"] { display: none; }

.st-key-listen { margin-top: .75rem; }
.st-key-listen button {
  min-height: 4rem; border-radius: var(--r-md) !important; border: 0 !important;
  background: var(--primary) !important; color: #fff !important;
  box-shadow: 0 1px 2px rgba(37, 99, 235, .25), 0 10px 24px -10px rgba(37, 99, 235, .55);
}
.st-key-listen button:hover { background: var(--primary-press) !important; }
.st-key-listen button p, .st-key-listen button [data-testid="stIconMaterial"] { font-size: 1.25rem !important; font-weight: 700; color: inherit !important; }
.st-key-listen button [data-testid="stIconMaterial"] { font-size: 1.625rem !important; }
.st-key-listen button:disabled { background: #EEF0F3 !important; color: #4B5563 !important; box-shadow: none; cursor: not-allowed; }
.ain-hint { text-align: center; color: var(--muted); font-size: 1rem; line-height: 1.7; margin: 0; text-wrap: balance; }
.ain-hint .ain-ic { font-size: 1.375rem; color: var(--primary); vertical-align: -.3em; margin-left: .375rem; }

.ain-alert {
  display: flex; gap: .75rem; align-items: flex-start;
  background: var(--danger-soft); border: 1px solid #FECACA; border-inline-start: 4px solid var(--danger);
  border-radius: var(--r-md); padding: 1rem 1.25rem; color: var(--ink); font-size: 1rem; line-height: 1.7;
}
.ain-alert .ain-ic { color: var(--danger); font-size: 1.5rem; }
.ain-alert strong { display: block; color: var(--danger-ink); font-weight: 700; margin-bottom: .125rem; }
.ain-alert code { direction: ltr; unicode-bidi: embed; background: #fff; padding: 0 .375rem; border-radius: 6px; font-size: .9em; }

.st-key-result_card {
  background: var(--bg); border: 1px solid var(--line); border-radius: var(--r-lg);
  box-shadow: var(--shadow); padding: 1.5rem; gap: 1.25rem; margin-top: .5rem;
  animation: ain-rise-a .45s cubic-bezier(.2, .7, .2, 1) both;
}
.st-key-result_card:has(.ain-anim-1) { animation-name: ain-rise-b; }
@keyframes ain-rise-a { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
@keyframes ain-rise-b { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }

.ain-result-head { display: flex; align-items: center; flex-wrap: wrap; gap: .5rem .75rem; margin-bottom: .875rem; }
.ain-result-label { display: inline-flex; align-items: center; gap: .5rem; color: var(--success-ink); font-weight: 700; font-size: 1rem; }
.ain-result-label::before { content: ""; width: .625rem; height: .625rem; border-radius: 50%; background: var(--success); }
.ain-result-meta { color: var(--muted); font-size: .875rem; }
.ain-result-text {
  font-size: 1.375rem; line-height: 1.95; font-weight: 500; color: var(--ink);
  border-inline-start: 4px solid var(--success); padding-inline-start: 1rem;
}
.st-key-result_card [data-testid="stMarkdownContainer"] .ain-result-text { font-size: 1.375rem; }

.ain-player { display: flex; flex-direction: column; gap: .875rem; }
.ain-player audio { width: 100%; height: 3.25rem; border-radius: 999px; }
.ain-actions { display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; }
.ain-btn {
  font: inherit; min-height: 3.25rem; padding: .5rem 1rem; cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center; gap: .5rem;
  background: var(--bg); color: var(--ink); border: 1.5px solid var(--line-strong); border-radius: 14px;
  font-size: 1rem; font-weight: 600;
}
.ain-btn:hover { background: var(--surface); border-color: #9CA3AF; }
.ain-btn:active { background: #EEF0F3; }
.ain-btn .ain-ic { font-size: 1.375rem; color: var(--primary); }
.ain-btn.is-done { border-color: var(--success); color: var(--success-ink); }
.ain-btn.is-done .ain-ic { color: var(--success-ink); }
.ain-note { color: var(--muted); font-size: .9375rem; margin: 0; }

.ain-ic {
  font-family: "Material Symbols Rounded"; font-weight: normal; font-style: normal; line-height: 1;
  letter-spacing: normal; text-transform: none; white-space: nowrap; direction: ltr;
  -webkit-font-feature-settings: "liga"; font-feature-settings: "liga"; user-select: none;
}
.ain-sr {
  position: absolute !important; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}

[data-testid="stMain"] [data-testid="stExpander"] { margin-top: 1.5rem; }
[data-testid="stMain"] [data-testid="stExpander"] details {
  border: 1px solid var(--line); border-radius: var(--r-md); background: var(--bg);
}
[data-testid="stMain"] [data-testid="stExpander"] summary { min-height: 3.5rem; padding: .5rem 1.25rem; border-radius: var(--r-md); }
[data-testid="stMain"] [data-testid="stExpander"] summary p { font-size: 1.0625rem; font-weight: 600; color: var(--ink); }
[data-testid="stMain"] [data-testid="stExpander"] summary:hover p { color: var(--primary); }
[data-testid="stMain"] [data-testid="stExpander"] summary [data-testid="stIconMaterial"] { color: var(--muted); }
.ain-past-mode { color: var(--muted); font-size: .875rem; font-weight: 600; margin: 0 0 .25rem; }
.ain-past-text { color: var(--ink); font-size: 1rem; line-height: 1.75; margin: 0; }
[data-testid="stExpanderDetails"] img { border-radius: var(--r-sm); border: 1px solid var(--line); }

[data-testid="stSidebar"] { background: var(--surface) !important; }
.ain-side-title { font-size: 1.5rem; font-weight: 700; color: var(--ink); margin: 0 0 .25rem; }
[data-testid="stSidebarUserContent"] { padding-top: .5rem; }
[data-testid="stCaptionContainer"] { opacity: 1 !important; }
[data-testid="stSidebarUserContent"] [data-testid="stCaptionContainer"] p { font-size: .9375rem; color: var(--muted); line-height: 1.7; }
.st-key-model_override input { direction: ltr; text-align: left; }

[data-testid="stCheckbox"] label:has(input[role="switch"]) > div:not([data-testid="stWidgetLabel"]) {
  box-shadow: inset 0 0 0 2px #6B7280; background: var(--bg) !important;
}
[data-testid="stCheckbox"] label:has(input[role="switch"]:not(:checked)) > div:not([data-testid="stWidgetLabel"]) > div {
  background: #6B7280 !important; box-shadow: none !important;
}
[data-testid="stCheckbox"] label:has(input[role="switch"]:checked) > div:not([data-testid="stWidgetLabel"]) {
  box-shadow: none; background: var(--primary) !important;
}
[data-testid="stCheckbox"] label:has(input:focus-visible) > div:not([data-testid="stWidgetLabel"]) {
  outline: 3px solid var(--primary); outline-offset: 3px;
}
[data-testid="stSidebarCollapseButton"] button { min-width: 48px; min-height: 48px; }
[data-testid="stSidebarUserContent"] [data-testid="stCheckbox"] label { min-height: 48px; align-items: center; gap: .75rem; }
[data-testid="stSidebarUserContent"] [data-testid="stCheckbox"] p { font-size: 1rem !important; }

[data-testid="stSpinner"] { justify-content: center; }
[data-testid="stSpinner"] p { font-size: 1.0625rem; color: var(--ink); }

@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding: 4.75rem 1rem 2rem; }
  .ain-title { font-size: 2.625rem; }
  .ain-logo { width: 2.625rem; height: 2.625rem; }
  .ain-logo span { width: .875rem; height: .875rem; }
  .ain-tagline { font-size: 1.0625rem; }
  .st-key-capture { padding: 1rem; border-radius: var(--r-md); }
  .st-key-result_card { padding: 1.25rem; }
  .ain-result-text { font-size: 1.375rem; }
  .st-key-listen {
    position: sticky; bottom: calc(.75rem + env(safe-area-inset-bottom)); z-index: 50;
  }
  .st-key-listen button { min-height: 4rem; box-shadow: 0 0 0 6px var(--bg), 0 12px 28px -8px rgba(17, 24, 39, .35); }
}
@media (max-width: 640px) {
  .st-key-modes [role="radiogroup"] { grid-template-columns: 1fr 1fr; }
  .st-key-modes [role="radiogroup"] > label { min-height: 4rem; padding: .75rem; justify-content: flex-start; }
  .st-key-modes [role="radiogroup"] > label p { flex-direction: row; text-align: right; gap: .625rem; }
  .st-key-modes [role="radiogroup"] > label p [role="img"] { font-size: 1.625rem; }
  .st-key-modes [role="radiogroup"] > label:last-child:nth-child(odd) { grid-column: 1 / -1; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
}
</style>
"""


def size_css(px: int) -> str:
    css = f"html {{ font-size: {px}px !important; }}"
    if px > FONT_SIZES["عادي"]:
        css += """
.st-key-modes [role="radiogroup"] { grid-template-columns: 1fr 1fr; }
.st-key-modes [role="radiogroup"] > label { min-height: 4rem; padding: .75rem; justify-content: flex-start; }
.st-key-modes [role="radiogroup"] > label p { flex-direction: row; text-align: right; gap: .625rem; }
.st-key-modes [role="radiogroup"] > label p [role="img"] { font-size: 1.625rem; }
.st-key-modes [role="radiogroup"] > label:last-child:nth-child(odd) { grid-column: 1 / -1; }
"""
    if px >= FONT_SIZES["كبير جداً"]:
        css += "@media (max-width: 640px) { .st-key-modes [role=\"radiogroup\"] { grid-template-columns: 1fr; } }"
    return f"<style>{css}</style>"


A11Y_JS = """
<script>
(() => {
  if (window.__ainA11y) return;
  window.__ainA11y = true;
  const label = (sel, text) => document.querySelectorAll(sel).forEach((el) => {
    if (el.getAttribute("aria-label") !== text) el.setAttribute("aria-label", text);
  });
  const fix = () => {
    document.documentElement.lang = "ar";
    label('[data-testid="stExpandSidebarButton"]', "افتح الإعدادات وحجم الخط");
    label('[data-testid="stSidebarCollapseButton"] button', "اقفل الإعدادات");
    label('[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"]', "اختار صورة من جهازك");
    label('[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-borderlessIcon"]', "اختار صورة تانية بدل دي");
    label('[data-testid="stFileChipDeleteBtn"] button, [data-testid="stFileUploaderDeleteBtn"] button', "شيل الصورة");
    document.querySelectorAll('[data-testid="stCameraInputButton"]').forEach((b) => {
      const state = /clear/i.test(b.textContent) ? "clear" : "take";
      if (b.dataset.ainState !== state) b.dataset.ainState = state;
      label('[data-testid="stCameraInputButton"][data-ain-state="' + state + '"]',
            state === "clear" ? "امسح الصورة وصوّر تاني" : "صوّر دلوقتي");
    });
  };
  fix();
  new MutationObserver(fix).observe(document.body, { childList: true, subtree: true, characterData: true });
})();
</script>
"""


def get_token() -> str | None:
    try:
        tok = st.secrets.get("HF_TOKEN")
        if tok:
            return tok
    except Exception:
        pass
    return os.environ.get("HF_TOKEN") or st.session_state.get("manual_token")


def get_models() -> list[str]:
    custom = None
    try:
        custom = st.secrets.get("MODEL_ID")
    except Exception:
        pass
    custom = st.session_state.get("model_override") or custom
    if custom:
        return [custom] + [m for m in DEFAULT_MODELS if m != custom]
    return DEFAULT_MODELS


def prepare_image(raw: bytes) -> tuple[str, Image.Image]:
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((1280, 1280))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}", img


def explain_error(err: Exception) -> str:
    msg = str(err)
    code = getattr(getattr(err, "response", None), "status_code", None)
    if code == 401 or "401" in msg or "Invalid credentials" in msg:
        return "التوكن غلط أو منتهي. اعمل توكن جديد من huggingface.co/settings/tokens وحطه في secrets.toml."
    if code == 403 or "403" in msg:
        return "التوكن مش معاه صلاحية Inference. اعمل توكن نوعه Fine-grained وفعّل خيار «Make calls to Inference Providers»."
    if code == 402 or "402" in msg or "credit" in msg.lower():
        return "الرصيد المجاني للشهر ده خلص على حساب Hugging Face. استنى الشهر الجاي أو اشحن رصيد."
    if code == 429 or "429" in msg:
        return "طلبات كتير في وقت قصير. استنى دقيقة وجرب تاني."
    return f"حصل خطأ: {msg[:250]}"


def ask_model(data_url: str, instruction: str) -> tuple[str, str]:
    token = get_token()
    if not token:
        raise RuntimeError("NO_TOKEN")
    client = InferenceClient(provider="auto", api_key=token, timeout=90)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": instruction},
            ],
        },
    ]
    last_err = None
    for model in get_models():
        try:
            out = client.chat.completions.create(
                model=model, messages=messages, max_tokens=500, temperature=0.2
            )
            text = (out.choices[0].message.content or "").strip()
            if text:
                return clean_for_speech(text), model
        except Exception as e:
            last_err = e
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code in (401, 402, 403):
                break
    raise last_err or RuntimeError("مفيش موديل رد.")


def clean_for_speech(text: str) -> str:
    for ch in ["**", "*", "#", "`", "_", "•"]:
        text = text.replace(ch, "")
    return text.strip()


@st.cache_data(show_spinner=False, max_entries=50)
def speak(text: str, slow: bool) -> bytes | None:
    try:
        buf = io.BytesIO()
        gTTS(text=text, lang="ar", slow=slow).write_to_fp(buf)
        return buf.getvalue()
    except Exception:
        return None


def alert_html(message: str) -> str:
    return (
        '<div class="ain-alert" role="alert"><span class="ain-ic" aria-hidden="true">error</span>'
        f"<div><strong>حصلت مشكلة</strong>{message}</div></div>"
    )


def player_html(audio: bytes | None, text: str, rid: int, autoplay: bool) -> str:
    copy_text = html.escape(text, quote=True)
    if audio:
        b64 = base64.b64encode(audio).decode()
        audio_part = (
            f'<audio controls preload="auto" aria-label="صوت الوصف" src="data:audio/mpeg;base64,{b64}"></audio>'
        )
        replay_btn = (
            '<button type="button" class="ain-btn" data-act="replay">'
            '<span class="ain-ic" aria-hidden="true">replay</span><span>اسمع تاني</span></button>'
        )
    else:
        audio_part = '<p class="ain-note">الصوت مش شغال دلوقتي (محتاج نت). الكلام مكتوب فوق.</p>'
        replay_btn = ""
    return f"""
<div class="ain-player" data-rid="{rid}">
  {audio_part}
  <div class="ain-actions">
    {replay_btn}
    <button type="button" class="ain-btn" data-act="copy" data-text="{copy_text}">
      <span class="ain-ic" aria-hidden="true">content_copy</span><span class="ain-btn-label">انسخ النص</span>
    </button>
  </div>
  <span class="ain-sr" aria-live="polite"></span>
</div>
<script>
(() => {{
  const root = document.querySelector('.ain-player[data-rid="{rid}"]:not([data-ready])');
  if (!root) return;
  root.dataset.ready = "1";
  const audio = root.querySelector("audio");
  const say = root.querySelector(".ain-sr");
  const replay = root.querySelector('[data-act="replay"]');
  const copy = root.querySelector('[data-act="copy"]');
  if (!root.querySelector('[data-act="replay"]')) root.querySelector(".ain-actions").style.gridTemplateColumns = "1fr";

  if (replay && audio) replay.addEventListener("click", () => {{
    audio.currentTime = 0;
    audio.play().catch(() => {{}});
  }});

  const copyText = async (t) => {{
    try {{ await navigator.clipboard.writeText(t); return true; }} catch (e) {{
      const ta = document.createElement("textarea");
      ta.value = t; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      let ok = false; try {{ ok = document.execCommand("copy"); }} catch (_) {{}}
      ta.remove(); return ok;
    }}
  }};
  copy.addEventListener("click", async () => {{
    const ok = await copyText(copy.dataset.text);
    const lbl = copy.querySelector(".ain-btn-label");
    const ic = copy.querySelector(".ain-ic");
    lbl.textContent = ok ? "النص اتنسخ" : "مقدرتش أنسخ";
    ic.textContent = ok ? "check" : "error";
    copy.classList.toggle("is-done", ok);
    say.textContent = ok ? "النص اتنسخ، تقدر تلزقه في أي مكان." : "مقدرتش أنسخ النص. حدّده وانسخه بإيدك.";
    clearTimeout(copy._t);
    copy._t = setTimeout(() => {{
      lbl.textContent = "انسخ النص"; ic.textContent = "content_copy"; copy.classList.remove("is-done");
    }}, 2500);
  }});

  if ({"true" if autoplay else "false"} && audio && window.__ainPlayed !== "{rid}") {{
    window.__ainPlayed = "{rid}";
    audio.play().catch(() => {{}});
  }}
}})();
</script>
"""


st.session_state.setdefault("history", [])
st.session_state.setdefault("last", None)
st.session_state.setdefault("results", 0)
if "font_size" not in st.session_state:
    saved = st.query_params.get("size")
    st.session_state.font_size = next((k for k, v in FONT_SIZE_PARAMS.items() if v == saved), "عادي")


with st.sidebar:
    st.html('<h2 class="ain-side-title">الإعدادات</h2>')
    font_size = st.radio("حجم الخط", list(FONT_SIZES.keys()), key="font_size")
    slow = st.toggle("صوت أبطأ", value=False)
    autoplay = st.toggle("شغّل الصوت تلقائياً", value=True)
    st.text_input(
        "موديل مختلف (اختياري)",
        key="model_override",
        placeholder="Qwen/Qwen2.5-VL-7B-Instruct",
        help="أي موديل رؤية على Hugging Face بيدعم chat completion.",
    )
    if not get_token():
        st.text_input("توكن Hugging Face", type="password", key="manual_token",
                      help="الأفضل تحطه في .streamlit/secrets.toml عشان متكتبوش كل مرة.")
    st.caption("عين مساعد، مش بديل عن الحذر. في الأدوية والطريق اتأكد دايماً.")

if FONT_SIZE_PARAMS[font_size] == "normal":
    st.query_params.pop("size", None)
else:
    st.query_params["size"] = FONT_SIZE_PARAMS[font_size]

with st.container(key="ain_css"):
    st.html(CSS + size_css(FONT_SIZES[font_size]))
with st.container(key="ain_js"):
    st.html(A11Y_JS, unsafe_allow_javascript=True)


st.html(
    """
<header class="ain-hero">
  <div class="ain-brand">
    <span class="ain-logo" aria-hidden="true"><span></span></span>
    <h1 class="ain-title">عين</h1>
  </div>
  <p class="ain-tagline">صوّر اللي قدامك أو ارفع صورة، وعين هتوصفهولك بالعربي وتقراهولك بصوت عالي.</p>
</header>
"""
)

with st.container(key="modes"):
    mode = st.radio(
        "عايز تعرف إيه؟",
        list(MODES.keys()),
        format_func=lambda m: f":material/{ICONS[m]}: {m}",
        horizontal=True,
        key="mode",
    )

with st.container(key="capture"):
    with st.container(key="src"):
        src = st.radio(
            "الصورة منين؟",
            list(SOURCES.keys()),
            format_func=lambda s: f":material/{SOURCES[s]}: {s}",
            horizontal=True,
        )
    if src == "الكاميرا":
        shot = st.camera_input("صوّر الحاجة اللي عايز تعرفها", label_visibility="collapsed")
    else:
        shot = st.file_uploader(
            "اختار صورة من جهازك", type=["jpg", "jpeg", "png", "webp"], label_visibility="collapsed"
        )

question = st.text_input(
    "عندك سؤال معيّن عن الصورة؟ (اختياري)",
    placeholder="مثلاً: الباب مفتوح ولا مقفول؟",
    key="question",
)

go = st.button("اسمع", icon=":material/volume_up:", type="primary", disabled=shot is None, key="listen", width="stretch")

if shot is None:
    st.html(
        '<p class="ain-hint"><span class="ain-ic" aria-hidden="true">info</span>'
        "صوّر بالكاميرا أو ارفع صورة، وبعدين دوس «اسمع».</p>"
    )

status = st.empty()

if go and shot is not None:
    instruction = MODES[mode]
    if question.strip():
        instruction += f"\n\nثم أجب على هذا السؤال بوضوح: {question.strip()}"
    try:
        data_url, img = prepare_image(shot.getvalue())
        with status, st.spinner("بشوف الصورة..."):
            t0 = time.time()
            answer, used = ask_model(data_url, instruction)
            secs = time.time() - t0
        status.empty()
        st.session_state.results += 1
        st.session_state.last = {
            "text": answer, "model": used, "secs": secs, "mode": mode, "rid": time.time_ns(),
        }
        st.session_state.history.insert(0, {"text": answer, "mode": mode, "thumb": img.copy()})
        st.session_state.history = st.session_state.history[:6]
    except RuntimeError as e:
        if str(e) == "NO_TOKEN":
            status.html(alert_html(
                "محتاج توكن Hugging Face. حطه في ملف <code>.streamlit/secrets.toml</code> "
                "أو افتح «الإعدادات» واكتبه هناك."
            ))
        else:
            status.html(alert_html(html.escape(explain_error(e))))
        st.session_state.last = None
    except Exception as e:
        status.html(alert_html(html.escape(explain_error(e))))
        st.session_state.last = None

last = st.session_state.last
if last:
    with st.container(key="result_card"):
        body = html.escape(last["text"]).replace("\n", "<br>")
        anim = st.session_state.results % 2
        st.markdown(
            f'<div class="ain-result-head"><span class="ain-result-label">النتيجة</span>'
            f'<span class="ain-result-meta">{html.escape(last["mode"])} · {last["secs"]:.1f} ثانية · '
            f'{html.escape(last["model"].split("/")[-1])}</span></div>'
            f'<div class="ain-result-text ain-anim-{anim}" role="status" aria-live="polite" aria-atomic="true">{body}</div>',
            unsafe_allow_html=True,
        )
        audio = speak(last["text"], slow)
        st.html(player_html(audio, last["text"], last["rid"], autoplay), unsafe_allow_javascript=True)

if len(st.session_state.history) > 1:
    with st.expander("اللي فات"):
        for item in st.session_state.history[1:]:
            c1, c2 = st.columns([1, 3], vertical_alignment="center")
            c1.image(item["thumb"], width="stretch")
            c2.html(
                f'<p class="ain-past-mode">{html.escape(item["mode"])}</p>'
                f'<p class="ain-past-text">{html.escape(item["text"])}</p>'
            )

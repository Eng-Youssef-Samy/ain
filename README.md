# عين — مساعد بصري لضعاف البصر

## التشغيل
1. اعمل توكن من https://huggingface.co/settings/tokens
   (نوعه Fine-grained وفعّل «Make calls to Inference Providers»)
2. انسخ `.streamlit/secrets.toml.example` وسمّيه `secrets.toml` وحط التوكن جواه.
3. ويندوز: دبل كليك على `run.bat`  |  ماك/لينكس: `./run.sh`
4. هيفتح على http://localhost:8501

## الموديل
الافتراضي `Qwen/Qwen2.5-VL-7B-Instruct`. لو مش متاح، التطبيق بيجرب بدايل تلقائياً.
تقدر تغيره من الشريط الجانبي أو `MODEL_ID` في secrets.toml.

ملاحظة: الكاميرا بتشتغل على localhost عادي. لو فتحته من موبايل على نفس الشبكة، المتصفح محتاج HTTPS، فاستخدم «رفع صورة».

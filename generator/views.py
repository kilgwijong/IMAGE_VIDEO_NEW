import os
import io
import uuid
import time
import random
from urllib.parse import urlparse
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required  # ✅ 추가

from PIL import Image
import requests
import google.generativeai as genai
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

def _clean(v):
    if not v:
        return v
    return str(v).lstrip("\ufeff").strip().strip('"').strip("'")

GOOGLE_API_KEY = _clean(os.getenv("GOOGLE_API_KEY"))
REPLICATE_API_TOKEN = _clean(os.getenv("REPLICATE_API_TOKEN"))

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY가 비어 있습니다. .env를 확인하세요.")
if not REPLICATE_API_TOKEN or not REPLICATE_API_TOKEN.startswith("r8_"):
    raise ValueError("REPLICATE_API_TOKEN이 비어있거나 형식이 올바르지 않습니다.")

genai.configure(api_key=GOOGLE_API_KEY)
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

SEEDANCE_MODEL = "bytedance/seedance-1-pro-fast"
RETRY_MAX = 3
DEFAULT_RETRY_AFTER = 12  # seconds

@login_required  # ✅ 로그인 필요
def index(request):
    return render(request, "generator/index.html")

@csrf_exempt
@login_required  # ✅ 로그인 필요
def generate_image(request):
    if request.method != "POST":
        return JsonResponse({"error": "잘못된 요청 방식입니다."}, status=400)

    prompt = (request.POST.get("prompt") or "").strip()
    files = request.FILES.getlist("images")

    if not prompt:
        return JsonResponse({"error": "프롬프트를 입력하세요."}, status=400)
    if not files:
        return JsonResponse({"error": "이미지를 1장 이상 업로드하세요."}, status=400)

    try:
        model = genai.GenerativeModel("gemini-2.5-flash-image")
        contents = [prompt]
        for f in files:
            img = Image.open(f)
            contents.append(img)

        resp = model.generate_content(contents)

        generated = None
        candidates = getattr(resp, "candidates", []) or []
        if candidates:
            parts = getattr(candidates[0].content, "parts", []) or []
            for p in parts:
                if getattr(p, "inline_data", None):
                    generated = p.inline_data.data
                    break

        if not generated:
            return JsonResponse({"error": "Gemini가 이미지를 반환하지 않았습니다."}, status=500)

        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        fname = f"{uuid.uuid4()}.png"
        fpath = os.path.join(settings.MEDIA_ROOT, fname)
        with open(fpath, "wb") as f:
            f.write(generated)

        return JsonResponse({"image_url": f"{settings.MEDIA_URL}{fname}"})
    except Exception as e:
        return JsonResponse({"error": f"이미지 생성 오류: {str(e)}"}, status=500)

def _sleep_with_retry_after(resp_or_seconds):
    secs = DEFAULT_RETRY_AFTER
    if isinstance(resp_or_seconds, requests.Response):
        ra = resp_or_seconds.headers.get("Retry-After")
        if ra:
            try:
                secs = int(float(ra))
            except Exception:
                secs = DEFAULT_RETRY_AFTER
    elif isinstance(resp_or_seconds, (int, float)):
        secs = int(resp_or_seconds)
    time.sleep(secs + random.uniform(0, 1.5))

def _replicate_upload_file(local_path: str, token: str) -> str:
    import mimetypes
    mime = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
    fname = os.path.basename(local_path)
    headers = {"Authorization": f"Token {token}"}

    with open(local_path, "rb") as rf:
        data_bytes = rf.read()
    if not data_bytes:
        raise RuntimeError("업로드 파일이 비어 있습니다.")

    def _post(payload):
        return requests.post(
            "https://api.replicate.com/v1/files",
            headers=headers,
            files=payload,
            timeout=120,
        )

    attempts = [
        lambda: {"file": (fname, open(local_path, "rb"), mime)},
        lambda: {"file": (fname, open(local_path, "rb"))},
        lambda: {"content": (fname, open(local_path, "rb"), mime)},
        lambda: {"file": (fname, io.BytesIO(data_bytes), mime)},
        lambda: {"file": (fname, io.BytesIO(data_bytes))},
        lambda: {"content": (fname, io.BytesIO(data_bytes), mime)},
    ]

    for _ in range(RETRY_MAX):
        last = None
        for make in attempts:
            files_payload = make()
            try:
                last = _post(files_payload)
                if 200 <= last.status_code < 300:
                    js = last.json()
                    url = (js.get("urls") or {}).get("get")
                    if not url:
                        raise RuntimeError(f"Replicate 업로드 응답에 URL이 없습니다: {js}")
                    return url
                if last.status_code == 402:
                    raise RuntimeError(
                        "Replicate 크레딧이 없습니다. 결제/충전을 완료한 뒤 다시 시도하세요."
                    )
                if last.status_code == 429:
                    _sleep_with_retry_after(last)
                    break
                if last.status_code == 400 and "Missing content" in (last.text or ""):
                    continue
                raise RuntimeError(f"/v1/files 업로드 실패: {last.status_code} {last.text}")
            finally:
                for v in files_payload.values():
                    if isinstance(v, tuple) and hasattr(v[1], "close"):
                        try:
                            v[1].close()
                        except Exception:
                            pass
    raise RuntimeError("레이트리밋/형식 문제로 파일 업로드 재시도 한도 초과")

@csrf_exempt
@login_required  # ✅ 로그인 필요
def generate_video(request):
    if request.method != "POST":
        return JsonResponse({"error": "잘못된 요청 방식입니다."}, status=400)

    prompt = (request.POST.get("prompt") or "").strip()
    image_url = (request.POST.get("image_url") or "").strip()
    if not image_url:
        return JsonResponse({"error": "image_url이 필요합니다."}, status=400)

    try:
        import replicate
        client = replicate.Client(api_token=REPLICATE_API_TOKEN)

        parsed = urlparse(image_url)
        filename = os.path.basename(parsed.path)
        local_path = os.path.join(settings.MEDIA_ROOT, filename)
        if not os.path.exists(local_path):
            return JsonResponse({"error": "서버에서 이미지 파일을 찾을 수 없습니다."}, status=404)
        if os.path.getsize(local_path) <= 0:
            return JsonResponse({"error": "업로드할 이미지 파일이 비어 있습니다."}, status=400)

        signed_url = _replicate_upload_file(local_path, REPLICATE_API_TOKEN)

        def _run_with_retries(model, model_input):
            last = None
            for _ in range(RETRY_MAX):
                try:
                    return client.run(model, input=model_input)
                except replicate.exceptions.ReplicateError as e:
                    msg = str(e)
                    if "status: 402" in msg or "insufficient credit" in msg.lower():
                        raise RuntimeError(
                            "Replicate 크레딧이 없습니다. https://replicate.com/account/billing#billing 에서 충전 후 다시 시도하세요."
                        )
                    if "status: 429" in msg or "throttled" in msg.lower():
                        _sleep_with_retry_after(DEFAULT_RETRY_AFTER)
                        last = e
                        continue
                    raise
            raise last or RuntimeError("예측 재시도 한도 초과")

        # 모델 제약: fps = 24 고정, 길이는 매우 짧음
        model_input = {
    "image": signed_url,
    "fps": 24,
    "num_frames": 24,          # 길이(아래 2번 참고)
    "target_resolution": "480p",
    "loop": False,
    "enable_reflection": False,
}
        
        if prompt:
            model_input["prompt"] = prompt

        output = _run_with_retries(SEEDANCE_MODEL, model_input)
        video_url = output[0] if isinstance(output, list) else output
        if not isinstance(video_url, str):
            return JsonResponse({"error": f"예상치 못한 응답: {output}"}, status=500)

        return JsonResponse({"video_url": video_url})

    except Exception as e:
        msg = str(e)
        if "422" in msg or "validation" in msg.lower() or "Input validation failed" in msg:
            return JsonResponse(
                {"error": "입력값이 모델 제약과 맞지 않습니다. fps는 24만 가능하고, num_frames는 16~24 범위 권장."},
                status=422,
            )
        if "크레딧" in msg or "billing" in msg.lower() or "402" in msg:
            return JsonResponse({"error": msg}, status=402)
        if "status: 404" in msg:
            return JsonResponse({"error": "Replicate에서 모델/파일 참조를 찾지 못했습니다."}, status=404)
        if "429" in msg or "throttled" in msg.lower():
            return JsonResponse({"error": "Replicate 레이트리밋입니다. 잠시 후 재시도."}, status=429)
        return JsonResponse({"error": f"영상 생성 오류: {msg}"}, status=500)

# ------------------------
# 새로 추가: 영상 저장/목록
# ------------------------

def _ensure_video_dir():
    video_dir = Path(settings.MEDIA_ROOT) / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)
    return video_dir

@csrf_exempt
@login_required  # ✅ 로그인 필요
def save_video(request):
    """
    프론트에서 받은 video_url(Replicate 결과)을 서버에 mp4로 저장
    """
    if request.method != "POST":
        return JsonResponse({"error": "잘못된 요청 방식입니다."}, status=400)

    video_url = (request.POST.get("video_url") or "").strip()
    if not video_url:
        return JsonResponse({"error": "video_url이 필요합니다."}, status=400)

    try:
        # 파일 다운로드
        r = requests.get(video_url, stream=True, timeout=180)
        if r.status_code != 200:
            return JsonResponse({"error": f"다운로드 실패: {r.status_code}"}, status=502)

        video_dir = _ensure_video_dir()
        fname = f"{uuid.uuid4()}.mp4"
        fpath = video_dir / fname

        with open(fpath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        saved_url = f"{settings.MEDIA_URL}videos/{fname}"
        return JsonResponse({"saved_video_url": saved_url})
    except Exception as e:
        return JsonResponse({"error": f"영상 저장 오류: {str(e)}"}, status=500)

@login_required  # ✅ 로그인 필요
def list_videos(request):
    """
    저장된 영상 목록 반환 (최신순)
    """
    video_dir = _ensure_video_dir()
    files = sorted(video_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    urls = [f"{settings.MEDIA_URL}videos/{p.name}" for p in files]
    return JsonResponse({"videos": urls})

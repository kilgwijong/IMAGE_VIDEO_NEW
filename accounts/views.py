# accounts/views.py
from typing import Optional
from datetime import datetime

from django.apps import apps
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Sum, Count
from django.views.generic import FormView



# --- 유틸: 관리자 체크 ---
def is_staff_or_superuser(u) -> bool:
    """활성화된 사용자 중 staff/superuser 또는 username == 'admin'."""
    return bool(u and u.is_active and (u.is_staff or u.is_superuser or u.username == "admin"))


def _safe_reverse(*names: str, fallback: str = "/") -> str:
    """
    URL 이름들을 순서대로 reverse 시도해서 성공하는 첫 번째를 반환.
    전부 실패하면 fallback 반환.
    """
    for name in names:
        try:
            return reverse(name)
        except Exception:
            continue
    return fallback


def _safe_next_url(request: HttpRequest) -> Optional[str]:
    """
    ?next= 파라미터가 있고 동일 출처이면 그걸 반환.
    (로그인 성공 후 사용)
    """
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return None


# --- 로그인 뷰: 관리자는 관리자 홈, 일반사용자는 사용자 홈 ---
class AdminAwareLoginView(FormView):
    template_name = "accounts/login.html"
    form_class = AuthenticationForm

    def form_valid(self, form):
        user = form.get_user()
        login(self.request, user)
        return redirect(self.get_success_url())

    def get_success_url(self) -> str:
        # 0) ?next= 우선 (동일 출처만 허용)
        next_url = _safe_next_url(self.request)
        if next_url:
            return next_url

        # 1) 관리자면 관리자 포털
        user = self.request.user
        if is_staff_or_superuser(user):
            return _safe_reverse("accounts:admin_home", fallback="/accounts/admin/")

        # 2) 일반 사용자면 사용자 홈 (여러 이름을 순차 시도)
        return _safe_reverse("home", "generator:home", "generator:index", fallback="/")


# --- 회원가입 ---
def signup(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("accounts:login")
    else:
        form = UserCreationForm()
    return render(request, "accounts/signup.html", {"form": form})


# --- 관리자 전용 데코레이터 ---
def staff_required(view_func):
    """로그인 + 관리자(staff/superuser/'admin')만 접근 가능."""
    return login_required(user_passes_test(is_staff_or_superuser)(view_func))


# --- 관리자 포털 화면들 ---
@staff_required
def admin_home(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/admin/home.html")


@staff_required
def admin_users(request: HttpRequest) -> HttpResponse:
    users = User.objects.all().order_by("-date_joined")
    return render(request, "accounts/admin/users.html", {"users": users})


@staff_required
def admin_user_edit(request: HttpRequest, user_id: int) -> HttpResponse:
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise Http404("해당 사용자를 찾을 수 없습니다.")

    if request.method == "POST":
        user.email = request.POST.get("email", user.email)
        user.is_active = True if request.POST.get("is_active") else False
        user.save()
        return redirect("accounts:admin_users")

    return render(request, "accounts/admin/user_edit.html", {"u": user})


@staff_required
def admin_user_delete(request: HttpRequest, user_id: int) -> HttpResponse:
    User.objects.filter(pk=user_id).delete()
    return redirect("accounts:admin_users")


@staff_required
def admin_billing(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/admin/billing.html")


@staff_required
def admin_api_usage(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/admin/api_usage.html")


# --- 사용자 마이페이지 ---
@login_required
def my_page(request: HttpRequest) -> HttpResponse:
    """
    사용자 마이페이지: 생성 기록, API 사용량, 예상 요금 표시.
    실제 모델이 없어도 에러 없이 렌더링됨.
    """
    user = request.user
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 1) 생성 기록 (이미지/영상)
    assets = []
    try:
        GeneratedAsset = apps.get_model("generator", "GeneratedAsset")
        assets = list(
            GeneratedAsset.objects.filter(user=user)
            .order_by("-created_at")[:20]
            .values("id", "kind", "prompt", "created_at", "status")
        )
    except Exception:
        assets = []

    # 2) API 사용량 / 비용
    usage_stats = {
        "month_calls": 0,
        "month_tokens": 0,
        "month_cost_won": 0,
        "avg_latency_ms": 0,
        "error_rate": 0,
    }
    daily_rows = []

    try:
        ApiUsageLog = apps.get_model("billing", "ApiUsageLog")
        qs = ApiUsageLog.objects.filter(user=user, created_at__gte=month_start)

        agg = qs.aggregate(
            month_calls=Count("id"),
            month_tokens=Sum("tokens"),
            month_cost_won=Sum("cost_won"),
        )
        usage_stats.update({k: agg.get(k) or 0 for k in usage_stats.keys()})

        # 일자별 그룹
        grouped = {}
        for row in qs.values("created_at", "tokens", "cost_won"):
            day = row["created_at"].date()
            grouped.setdefault(day, {"tokens": 0, "cost_won": 0, "calls": 0})
            grouped[day]["tokens"] += row.get("tokens") or 0
            grouped[day]["cost_won"] += row.get("cost_won") or 0
            grouped[day]["calls"] += 1

        daily_rows = sorted(
            [{"day": d, **v} for d, v in grouped.items()],
            key=lambda x: x["day"],
            reverse=True,
        )[:14]
    except Exception:
        pass

    context = {
        "assets": assets,
        "usage": usage_stats,
        "daily_rows": daily_rows,
    }
    return render(request, "accounts/mypage.html", context)

# accounts/urls.py
from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

app_name = "accounts"

urlpatterns = [
    # 로그인/로그아웃/회원가입
    path("login/",  views.AdminAwareLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="accounts:login"), name="logout"),
    path("signup/", views.signup, name="signup"),

    # 마이페이지 ⭐
    path("me/", views.my_page, name="mypage"),

    # 관리자 포털
    path("admin/", views.admin_home, name="admin_home"),
    path("admin/users/", views.admin_users, name="admin_users"),
    path("admin/users/<int:user_id>/edit/", views.admin_user_edit, name="admin_user_edit"),
    path("admin/users/<int:user_id>/delete/", views.admin_user_delete, name="admin_user_delete"),
    path("admin/billing/", views.admin_billing, name="admin_billing"),
    path("admin/api-usage/", views.admin_api_usage, name="admin_api_usage"),
]

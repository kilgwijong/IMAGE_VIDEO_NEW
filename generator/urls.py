# generator/urls.py
from django.urls import path
from . import views

app_name = "generator"

urlpatterns = [
    # 기존 홈(루트) - 그대로 둡니다
    path("", views.index, name="index"),

    # ✅ 추가: 'home' 이름을 찾는 코드가 있어도 안전하게 매핑되도록 별칭 제공
    path("home/", views.index, name="home"),

    # 이미지/영상 API들 (기존 그대로)
    path("generate-image/", views.generate_image, name="generate_image"),
    path("generate-video/", views.generate_video, name="generate_video"),
    path("save-video/", views.save_video, name="save_video"),
    path("list-videos/", views.list_videos, name="list_videos"),
]

from fastapi import APIRouter

from services.auth_serivce import (
    forgot_password,
    login,
    logout,
    refresh,
    resend_signup_otp,
    reset_password,
    signup,
    verify_signup_otp,
)

router = APIRouter()

# Public routes
router.add_api_route("/signup", signup, methods=["POST"])
router.add_api_route("/signup/verify-otp", verify_signup_otp, methods=["POST"])
router.add_api_route("/signup/resend-otp", resend_signup_otp, methods=["POST"])
router.add_api_route("/login", login, methods=["POST"])
router.add_api_route("/refresh", refresh, methods=["POST"])
router.add_api_route("/logout", logout, methods=["POST"])
router.add_api_route("/forgot-password", forgot_password, methods=["POST"])
router.add_api_route("/reset-password", reset_password, methods=["POST"])

import subprocess
import sys


def test_network_guard_blocks_requests_import():
    code = (
        "from pyq_subject_classifier.config import install_network_guard, NetworkGuardError\n"
        "install_network_guard()\n"
        "try:\n"
        "    import requests\n"
        "    print('IMPORT_SUCCEEDED')\n"
        "except NetworkGuardError:\n"
        "    print('BLOCKED')\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    assert "BLOCKED" in result.stdout


def test_network_guard_blocks_openai_sdk():
    code = (
        "from pyq_subject_classifier.config import install_network_guard, NetworkGuardError\n"
        "install_network_guard()\n"
        "try:\n"
        "    import openai\n"
        "    print('IMPORT_SUCCEEDED')\n"
        "except NetworkGuardError:\n"
        "    print('BLOCKED')\n"
        "except ModuleNotFoundError:\n"
        "    print('BLOCKED')\n"  # not installed at all is equally safe
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    assert "BLOCKED" in result.stdout

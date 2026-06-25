def test_gpu_runtime_manifest_disallows_cpu_fallback():
    import json
    from pathlib import Path

    manifest = json.loads(
        Path("tools/tts/cosyvoice_gpu_runtime.json").read_text(encoding="utf-8")
    )

    assert manifest["profile"] == "cuda128_rtx50_ape_verified"
    assert manifest["backend"] == "cuda"
    assert manifest["allow_cpu_fallback"] is False
    assert manifest["cuda_index_url"].endswith("/cu128")
    assert manifest["torch"] == "2.11.*"
    assert manifest["torchaudio"] == "2.11.*"
    assert manifest["expected_cuda"] == "12.8"
    assert manifest["expected_device_capability"] == "sm_120"

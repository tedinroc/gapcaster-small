import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    lang: str = "en"
    # Gap map
    merge_pause: float = 0.6        # pauses shorter than this stay inside a dialogue span
    lead: float = 0.25              # silence kept after dialogue ends
    tail: float = 0.30              # silence kept before dialogue resumes
    min_slot: float = 1.1           # shortest window worth narrating
    breath: float = 0.8             # minimum quiet between two AD lines
    max_slot: float = 7.0           # long silences are split at shot boundaries
    # Writing budget
    words_per_sec: float = 2.6      # first-guess speaking rate for the budget (English, words)
    chars_per_sec: float = 4.0      # Mandarin budget in characters per second (Kokoro zf_xiaobei speaks about 4.3)
    # Fit loop
    speeds: tuple = (1.0, 1.08, 1.15)
    max_rewrites: int = 3
    # Models
    whisper_model: str = "mlx-community/whisper-large-v3-turbo"
    # Hugging Face repo id or a local folder (set GAPCASTER_VLM to use a copy already on disk).
    # Human-Scale default: Qwen3.5-9B-8bit (≤10B early-fusion VLM, ~13.1 GB peak on Apple Silicon).
    # Qwen3-VL-8B-Instruct-8bit (8B) and Qwen3.8-27B-MLX-8bit (27B reference) are also supported:
    #   GAPCASTER_VLM=mlx-community/Qwen3-VL-8B-Instruct-8bit
    vlm_model: str = os.environ.get("GAPCASTER_VLM", "mlx-community/Qwen3.5-9B-8bit")
    tts_model: str = "mlx-community/Kokoro-82M-bf16"
    tts_voice: str = "af_heart"
    tts_ref_audio: str = ""                  # optional reference wav for qwen3_tts (defaults to bundled Apache-2.0 zh-TW voice)
    tts_ref_text: str = ""                   # optional reference transcript for qwen3_tts
    llm_backend: str = "mlx"        # "mlx" (in-process, Mac) or "openai" (any OpenAI-compatible server, e.g. vLLM on Arc Pro B70)
    llm_base_url: str = "http://127.0.0.1:8000/v1"
    llm_model_name: str = "qwen"             # must match vLLM --served-model-name
    concurrency: int = 8                     # parallel requests to an OpenAI-compatible server
    asr_backend: str = "mlx"                 # "mlx" (mlx-whisper) or "openvino" (OpenVINO GenAI WhisperPipeline)
    asr_ov_model: str = os.environ.get("GAPCASTER_OV_WHISPER", "OpenVINO/whisper-large-v3-turbo-int8-ov")
    asr_device: str = "CPU"                  # OpenVINO device: CPU or GPU (Arc)
    tts_backend: str = "mlx"                 # "qwen3_tts" (Apache-2.0 MLX zh-TW), "avspeech" (macOS fallback), "mlx" (Kokoro), or "kokoro" (CPU/XPU)
    extra: dict = field(default_factory=dict)

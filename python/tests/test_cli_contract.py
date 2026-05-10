from kokoro_rocm.cli import build_parser


def test_default_say_parser_accepts_output():
    args = build_parser().parse_args(["-o", "/tmp/a.wav"])
    assert args.output == "/tmp/a.wav"
    assert args.command is None


def test_explicit_say_parser_accepts_output():
    args = build_parser().parse_args(
        ["say", "-o", "/tmp/a.wav", "--target-wpm", "500", "--precision", "fp16", "--profile-output", "/tmp/a.profile.json"]
    )
    assert args.command == "say"
    assert args.target_wpm == 500
    assert args.precision == "fp16"
    assert args.profile_output == "/tmp/a.profile.json"

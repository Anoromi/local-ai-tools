{
  description = "Kokoro PyTorch ROCm daemon CLI";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
      };
      python = pkgs.python312;
      runtimePath = pkgs.lib.makeBinPath [
        pkgs.bun
        pkgs.uv
        pkgs.ffmpeg
        pkgs.sox
        pkgs.espeak-ng
        pkgs.gcc
        pkgs.curl
      ];
      ldPath = pkgs.lib.makeLibraryPath [
        pkgs.stdenv.cc.cc.lib
        pkgs.zlib
        pkgs.libsndfile
      ];
      source = builtins.path {
        path = ./.;
        name = "local-ai-tools-source";
      };
      bunDeps = pkgs.stdenvNoCC.mkDerivation {
        pname = "local-ai-tools-bun-deps";
        version = "0.1.0";
        src = source;
        nativeBuildInputs = [ pkgs.bun ];
        outputHashMode = "recursive";
        outputHashAlgo = "sha256";
        outputHash = "sha256-wiqklJnxhK62pAdiA3CdZ5fipbtQHizm5W9FBfBNAj0=";
        dontFixup = true;
        buildPhase = ''
          runHook preBuild
          export HOME="$TMPDIR"
          bun install --no-save
          runHook postBuild
        '';
        installPhase = ''
          runHook preInstall
          mkdir -p "$out"
          cp -R node_modules "$out/node_modules"
          if [ -d apps/cli/node_modules ]; then
            mkdir -p "$out/apps/cli"
            cp -R apps/cli/node_modules "$out/apps/cli/node_modules"
          fi
          if [ -d packages/protocol/node_modules ]; then
            mkdir -p "$out/packages/protocol"
            cp -R packages/protocol/node_modules "$out/packages/protocol/node_modules"
          fi
          runHook postInstall
        '';
      };
      local-ai-tools = pkgs.stdenvNoCC.mkDerivation {
        pname = "local-ai-tools";
        version = "0.1.0";
        src = source;
        nativeBuildInputs = [ pkgs.makeWrapper pkgs.bun ];
        buildPhase = ''
          runHook preBuild
          export HOME="$TMPDIR"
          cp -R ${bunDeps}/node_modules ./node_modules
          if [ -d ${bunDeps}/apps/cli/node_modules ]; then
            mkdir -p apps/cli
            cp -R ${bunDeps}/apps/cli/node_modules apps/cli/node_modules
          fi
          if [ -d ${bunDeps}/packages/protocol/node_modules ]; then
            mkdir -p packages/protocol
            cp -R ${bunDeps}/packages/protocol/node_modules packages/protocol/node_modules
          fi
          chmod -R u+w ./node_modules
          [ -d apps/cli/node_modules ] && chmod -R u+w apps/cli/node_modules
          [ -d packages/protocol/node_modules ] && chmod -R u+w packages/protocol/node_modules
          mkdir -p packages/protocol/dist apps/cli/dist
          bun build packages/protocol/src/index.ts packages/protocol/src/schema.ts packages/protocol/src/encode.ts \
            --target=node \
            --outdir packages/protocol/dist
          bun build apps/cli/src/main.ts \
            --target=bun \
            --outfile apps/cli/dist/local-ai-tools.js
          runHook postBuild
        '';
        installPhase = ''
          runHook preInstall
          mkdir -p "$out/share/local-ai-tools/dist" "$out/share/local-ai-tools/python" "$out/bin"
          cp apps/cli/dist/local-ai-tools.js "$out/share/local-ai-tools/dist/local-ai-tools.js"
          cp -R python/src "$out/share/local-ai-tools/python/src"
          makeWrapper ${pkgs.bun}/bin/bun "$out/bin/local-ai-tools" \
            --add-flags "$out/share/local-ai-tools/dist/local-ai-tools.js" \
            --prefix PATH : "${runtimePath}" \
            --prefix LD_LIBRARY_PATH : "${ldPath}:/tmp/kokoro-bench/kokoro-pytorch-rocm/.venv/lib/python3.12/site-packages/_rocm_sdk_core/lib" \
            --set-default LOCAL_AI_TOOLS_PYTHON "/tmp/kokoro-bench/kokoro-pytorch-rocm/.venv/bin/python" \
            --set-default LOCAL_AI_TOOLS_PYTHONPATH "$out/share/local-ai-tools/python/src" \
            --set-default LOCAL_AI_TOOLS_PYTHON_HELPER "$out/bin/local-ai-tools-python" \
            --set-default HIP_VISIBLE_DEVICES "0" \
            --set-default ROCR_VISIBLE_DEVICES "0" \
            --set-default PYTORCH_ROCM_ARCH "gfx1151" \
            --set-default HSA_OVERRIDE_GFX_VERSION "11.5.1" \
            --set-default TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL "1" \
            --set-default TORCH_COMPILE_DISABLE "1" \
            --set-default TORCHDYNAMO_DISABLE "1" \
            --set-default PROJECT_TRANSFORMERS_PATH "/home/anoromi/code/my/testing-site/text-selection-tunings/.venv/lib/python3.12/site-packages" \
            --set-default HF_HUB_DISABLE_TELEMETRY "1" \
            --set-default TOKENIZERS_PARALLELISM "false"
          makeWrapper ${python}/bin/python "$out/bin/local-ai-tools-python" \
            --prefix PYTHONPATH : "$out/share/local-ai-tools/python/src" \
            --prefix PATH : "${runtimePath}" \
            --prefix LD_LIBRARY_PATH : "${ldPath}:/tmp/kokoro-bench/kokoro-pytorch-rocm/.venv/lib/python3.12/site-packages/_rocm_sdk_core/lib" \
            --set-default LOCAL_AI_TOOLS_PYTHON "/tmp/kokoro-bench/kokoro-pytorch-rocm/.venv/bin/python" \
            --set-default HIP_VISIBLE_DEVICES "0" \
            --set-default ROCR_VISIBLE_DEVICES "0" \
            --set-default PYTORCH_ROCM_ARCH "gfx1151" \
            --set-default HSA_OVERRIDE_GFX_VERSION "11.5.1" \
            --set-default TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL "1" \
            --set-default TORCH_COMPILE_DISABLE "1" \
            --set-default TORCHDYNAMO_DISABLE "1" \
            --set-default PROJECT_TRANSFORMERS_PATH "/home/anoromi/code/my/testing-site/text-selection-tunings/.venv/lib/python3.12/site-packages" \
            --set-default HF_HUB_DISABLE_TELEMETRY "1" \
            --set-default TOKENIZERS_PARALLELISM "false" \
            --add-flags "-m local_ai_tools"
          runHook postInstall
        '';
      };
    in {
      packages.${system} = {
        local-ai-tools = local-ai-tools;
        default = local-ai-tools;
      };

      apps.${system} = {
        local-ai-tools = {
          type = "app";
          program = "${local-ai-tools}/bin/local-ai-tools";
        };
        default = self.apps.${system}.local-ai-tools;
      };

      devShells.${system}.default = pkgs.mkShell {
        packages = with pkgs; [
          bun
          nodejs_22
          uv
          python312
          ffmpeg
          sox
          libsndfile
          espeak-ng
          git
          git-lfs
          gh
          pkg-config
          cmake
          ninja
          gcc
          stdenv.cc.cc.lib
          jq
          curl
          cacert
          zlib
        ];

        shellHook = ''
          export UV_PROJECT_ENVIRONMENT="$PWD/python/.venv"
          export LOCAL_AI_TOOLS_PYTHON="''${LOCAL_AI_TOOLS_PYTHON:-/tmp/kokoro-bench/kokoro-pytorch-rocm/.venv/bin/python}"
          export HIP_VISIBLE_DEVICES="''${HIP_VISIBLE_DEVICES:-0}"
          export ROCR_VISIBLE_DEVICES="''${ROCR_VISIBLE_DEVICES:-0}"
          export PYTORCH_ROCM_ARCH="''${PYTORCH_ROCM_ARCH:-gfx1151}"
          export HSA_OVERRIDE_GFX_VERSION="''${HSA_OVERRIDE_GFX_VERSION:-11.5.1}"
          export TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL="''${TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL:-1}"
          export TORCH_COMPILE_DISABLE="''${TORCH_COMPILE_DISABLE:-1}"
          export TORCHDYNAMO_DISABLE="''${TORCHDYNAMO_DISABLE:-1}"
          export PROJECT_TRANSFORMERS_PATH="''${PROJECT_TRANSFORMERS_PATH:-/home/anoromi/code/my/testing-site/text-selection-tunings/.venv/lib/python3.12/site-packages}"
          export HF_HUB_DISABLE_TELEMETRY=1
          export TOKENIZERS_PARALLELISM=false
          export LD_LIBRARY_PATH="${ldPath}:/tmp/kokoro-bench/kokoro-pytorch-rocm/.venv/lib/python3.12/site-packages/_rocm_sdk_core/lib:''${LD_LIBRARY_PATH:-}"
          echo "local-ai-tools dev shell"
          echo "Run: bun install"
          echo "Then: bun run build && cd python && uv sync --dev"
        '';
      };
    };
}

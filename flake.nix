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
      bunDeps = pkgs.stdenvNoCC.mkDerivation {
        pname = "kokoro-rocm-bun-deps";
        version = "0.1.0";
        src = ./.;
        nativeBuildInputs = [ pkgs.bun ];
        outputHashMode = "recursive";
        outputHashAlgo = "sha256";
        outputHash = "sha256-2J3JsO2+Ah//bN3AOux4bk2NN3zX69ou3r8xwM9+cuo=";
        dontFixup = true;
        buildPhase = ''
          runHook preBuild
          export HOME="$TMPDIR"
          bun install --frozen-lockfile
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
      kokoro-rocm = pkgs.stdenvNoCC.mkDerivation {
        pname = "kokoro-rocm";
        version = "0.1.0";
        src = ./.;
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
            --outfile apps/cli/dist/kokoro-rocm.js
          runHook postBuild
        '';
        installPhase = ''
          runHook preInstall
          mkdir -p "$out/share/kokoro-rocm/dist" "$out/share/kokoro-rocm/python" "$out/bin"
          cp apps/cli/dist/kokoro-rocm.js "$out/share/kokoro-rocm/dist/kokoro-rocm.js"
          cp -R python/src "$out/share/kokoro-rocm/python/src"
          makeWrapper ${pkgs.bun}/bin/bun "$out/bin/kokoro-rocm" \
            --add-flags "$out/share/kokoro-rocm/dist/kokoro-rocm.js" \
            --prefix PATH : "${runtimePath}" \
            --prefix LD_LIBRARY_PATH : "${ldPath}:/tmp/kokoro-bench/kokoro-pytorch-rocm/.venv/lib/python3.12/site-packages/_rocm_sdk_core/lib" \
            --set-default KOKORO_ROCM_PYTHON "/tmp/kokoro-bench/kokoro-pytorch-rocm/.venv/bin/python" \
            --set-default KOKORO_ROCM_PYTHONPATH "$out/share/kokoro-rocm/python/src" \
            --set-default KOKORO_ROCM_PYTHON_HELPER "$out/bin/kokoro-rocm-python" \
            --set-default HIP_VISIBLE_DEVICES "0" \
            --set-default ROCR_VISIBLE_DEVICES "0" \
            --set-default PYTORCH_ROCM_ARCH "gfx1151" \
            --set-default HSA_OVERRIDE_GFX_VERSION "11.5.1" \
            --set-default HF_HUB_DISABLE_TELEMETRY "1" \
            --set-default TOKENIZERS_PARALLELISM "false"
          makeWrapper ${python}/bin/python "$out/bin/kokoro-rocm-python" \
            --prefix PYTHONPATH : "$out/share/kokoro-rocm/python/src" \
            --prefix PATH : "${runtimePath}" \
            --prefix LD_LIBRARY_PATH : "${ldPath}:/tmp/kokoro-bench/kokoro-pytorch-rocm/.venv/lib/python3.12/site-packages/_rocm_sdk_core/lib" \
            --set-default KOKORO_ROCM_PYTHON "/tmp/kokoro-bench/kokoro-pytorch-rocm/.venv/bin/python" \
            --set-default HIP_VISIBLE_DEVICES "0" \
            --set-default ROCR_VISIBLE_DEVICES "0" \
            --set-default PYTORCH_ROCM_ARCH "gfx1151" \
            --set-default HSA_OVERRIDE_GFX_VERSION "11.5.1" \
            --set-default HF_HUB_DISABLE_TELEMETRY "1" \
            --set-default TOKENIZERS_PARALLELISM "false" \
            --add-flags "-m kokoro_rocm"
          runHook postInstall
        '';
      };
    in {
      packages.${system} = {
        kokoro-rocm = kokoro-rocm;
        default = kokoro-rocm;
      };

      apps.${system} = {
        kokoro-rocm = {
          type = "app";
          program = "${kokoro-rocm}/bin/kokoro-rocm";
        };
        default = self.apps.${system}.kokoro-rocm;
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
          export KOKORO_ROCM_PYTHON="''${KOKORO_ROCM_PYTHON:-/tmp/kokoro-bench/kokoro-pytorch-rocm/.venv/bin/python}"
          export HIP_VISIBLE_DEVICES="''${HIP_VISIBLE_DEVICES:-0}"
          export ROCR_VISIBLE_DEVICES="''${ROCR_VISIBLE_DEVICES:-0}"
          export PYTORCH_ROCM_ARCH="''${PYTORCH_ROCM_ARCH:-gfx1151}"
          export HSA_OVERRIDE_GFX_VERSION="''${HSA_OVERRIDE_GFX_VERSION:-11.5.1}"
          export HF_HUB_DISABLE_TELEMETRY=1
          export TOKENIZERS_PARALLELISM=false
          export LD_LIBRARY_PATH="${ldPath}:/tmp/kokoro-bench/kokoro-pytorch-rocm/.venv/lib/python3.12/site-packages/_rocm_sdk_core/lib:''${LD_LIBRARY_PATH:-}"
          echo "kokoro-rocm dev shell"
          echo "Run: bun install"
          echo "Then: bun run build && cd python && uv sync --dev"
        '';
      };
    };
}

{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      inherit (pkgs) lib;

      python = pkgs.python3.withPackages (ps: with ps; [
        pillow
        starlette
        uvicorn
        httpx
        jinja2
        python-multipart
      ]);

      src = lib.fileset.toSource {
        root = ./.;
        fileset = lib.fileset.unions [ ./main.py ./index.html ./overlays ];
      };

      app = pkgs.runCommand "afd-icon" { } ''
        mkdir -p $out/app
        cp -r ${src}/. $out/app
      '';
    in
    {
      packages.${system} = rec {
        default = image;
        image = pkgs.dockerTools.streamLayeredImage {
          name = "afd-icon";
          contents = [ python app ];
          config = {
            WorkingDir = "/app";
            Cmd = [ "uvicorn" "main:app" "--host" "::" "--port" "8000" ];
          };
        };
      };
    };
}

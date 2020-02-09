{ nixpkgs ? import ./nix/nixpkgs.nix }:
let
  pkgs = import nixpkgs {};
  pythonPackages = pkgs.python3Packages;

  # it’s not yet in nixpkgs
  update-copyright = with pythonPackages; buildPythonApplication rec {
    pname = "update-copyright";
    version = "0.6.2";
    src = fetchPypi {
      inherit pname version;
      sha256 = "17ybdgbdc62yqhda4kfy1vcs1yzp78d91qfhj5zbvz1afvmvdk7z";
    };
    meta = with pkgs.lib; {
      description = "An automatic copyright update tool";
      license = licenses.gpl3;
    };
  };

in pkgs.mkShell {
  buildInputs = with pythonPackages; [
    pkgs.python3
    feedparser
    html2text
    parameterized
    update-copyright pkgs.git
  ];
}

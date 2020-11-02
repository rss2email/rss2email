{ nixpkgs ? import ./nix/nixpkgs.nix }:
let
  pkgs = import nixpkgs {};
  pythonEnv = pkgs.poetry2nix.mkPoetryEnv {
    projectDir = ./.;
  };
in pkgs.mkShell {
  buildInputs = with pkgs; [
    poetry
    pythonEnv
    git
  ];
}

{ nixpkgs ? import ./nixpkgs.nix }:
let
  pkgs = import nixpkgs {};

  supportedPackageSets = [
    { version = "3_5"; set = pkgs.python35Packages; }
    { version = "3_6"; set = pkgs.python36Packages; }
    { version = "3_7"; set = pkgs.python37Packages; }
  ];

  src = pkgs.lib.cleanSource ../.;

  mkName = version: "rss2email-python_${version}";

  buildWith = pkgSet: pkgSet.set.buildPythonApplication {
    name = mkName pkgSet.version;
    version = "develop";

    inherit src;
    propagatedBuildInputs = with pkgSet.set; [
      feedparser
      html2text
      # tests
      beautifulsoup4
    ];

    checkPhase = ''
      env PYTHONPATH=.:$PYTHONPATH \
        python3 ./test/test.py
    '';

  };

in
  # { "rss2email-3-5" = <rss2email package>; … }
  pkgs.lib.listToAttrs
    (map
      (pkgSet: pkgs.lib.nameValuePair
         (mkName pkgSet.version)
         (buildWith pkgSet))
      supportedPackageSets)

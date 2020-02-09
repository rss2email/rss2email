{ nixpkgs ? import ./nixpkgs.nix }:
let
  pkgs = import nixpkgs {};

  supportedPackageSets = [
    { version = "3_5"; set = pkgs.python35Packages; }
    { version = "3_6"; set = pkgs.python36Packages; }
    { version = "3_7"; set = pkgs.python37Packages; }
    { version = "3_8"; set = pkgs.python38Packages; }
  ];
  latestSupportedPackageSet = pkgs.lib.last supportedPackageSets;

  src = pkgs.lib.cleanSource ../.;

  mkName = version: "rss2email-python_${version}";

  buildWith = pkgSet: pkgSet.set.buildPythonApplication {
    name = mkName pkgSet.version;
    version = "develop";

    inherit src;
    checkInputs = with pkgSet.set; [
      parameterized
    ];
    propagatedBuildInputs = with pkgSet.set; [
      feedparser
      html2text
    ];

    doCheck = true;
    checkPhase = ''
      env \
        PATH="$out/bin:$PATH" \
        PYTHONPATH=.:"$PYTHONPATH" \
          python3 ./test/test.py --verbose
    '';
  };

  # { "rss2email-python_3_5" = <rss2email package>; … }
  rss2emailVersions =
    (pkgs.lib.listToAttrs
      (map
        (pkgSet: pkgs.lib.nameValuePair
          (mkName pkgSet.version)
          (buildWith pkgSet))
        supportedPackageSets));

in {
  rss2email = buildWith latestSupportedPackageSet;

  pythonVersions = rss2emailVersions;
}

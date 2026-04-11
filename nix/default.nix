{ pkgs ? import <nixpkgs> {} }:

let 
  callXonshPackage = pkgs.callPackage ./package.nix;
in
{
  default = callXonshPackage { };
  xonsh = callXonshPackage { };
  xonsh-py311 = callXonshPackage { python3 = pkgs.python311; };
  xonsh-py312 = callXonshPackage { python3 = pkgs.python312; };
  xonsh-py313 = callXonshPackage { python3 = pkgs.python313; };
  xonsh-py314 = callXonshPackage { python3 = pkgs.python314; };
}

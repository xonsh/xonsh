{
  description = "Xonsh shell";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    systems.url = "github:nix-systems/default";
  };
  outputs = { self, nixpkgs, systems }:
  let
    inherit (nixpkgs) lib;
    eachSystem = lib.genAttrs (import systems);
  in {
    packages = eachSystem (system: import ./nix {
      pkgs = nixpkgs.legacyPackages."${system}";
    });
  };
}

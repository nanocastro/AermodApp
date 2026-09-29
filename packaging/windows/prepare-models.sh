#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
work="${RUNNER_TEMP:-/tmp}/aermod-windows-models"
runtime="$root/packaging/windows/runtime/bin"
rm -rf "$work"
mkdir -p "$work" "$runtime"

download() {
  local url="$1" output="$2" expected="$3"
  curl -fsSL "$url" -o "$output"
  echo "$expected  $output" | sha256sum --check --status
}

download "https://gaftp.epa.gov/Air/aqmg/SCRAM/models/preferred/aermod/aermod_source.zip" "$work/aermod.zip" "5092c1d68b77d9407c9f67d497b440a79d2ee746f9ed6515a63ad4a5b11cd8ed"
download "https://gaftp.epa.gov/Air/aqmg/SCRAM/models/screening/aerscreen/makemet_code.zip" "$work/makemet.zip" "c9f3be6b44d82681168b41673a96c31b6c8ac78de36a0627b5473c60360a9f62"
download "https://gaftp.epa.gov/Air/aqmg/SCRAM/models/related/aermap/aermap_source.zip" "$work/aermap.zip" "4b34b39fe0039db114e3e78e3b6faa4797a5f8ee8ca0771db030a9b93ab3bed6"
download "https://gaftp.epa.gov/Air/aqmg/SCRAM/models/related/bpip/bpipprime.zip" "$work/bpip.zip" "a51a93fc8c306065830ded33772ad473fed9d10114dd5b317026c5616b21ed6f"

unzip -q "$work/aermod.zip" -d "$work/aermod"
unzip -q "$work/makemet.zip" -d "$work/makemet"
unzip -q "$work/aermap.zip" -d "$work/aermap"
unzip -q "$work/bpip.zip" -d "$work/bpip"

aermod_dir="$(find "$work/aermod" -type f -iname aermod.f -printf '%h\n' | head -1)"
pushd "$aermod_dir" >/dev/null
objects=(modules grsm aermod setup coset soset reset meset ouset inpsum metext iblval siggrid tempgrid windgrid calc1 calc2 prise arise prime sigmas pitarea uninam output evset evcalc evoutput rline bline)
for source in "${objects[@]}"; do gfortran -c -fbounds-check -Wuninitialized -O2 -static "${source}.f"; done
gfortran -static -O2 -o "$runtime/aermod.exe" "${objects[@]/%/.o}"
popd >/dev/null

makemet_source="$(find "$work/makemet" -type f -iname 'MAKEMET.FOR' | head -1)"
gfortran -static -O2 -std=legacy -o "$runtime/makemet.exe" "$makemet_source"

aermap_dir="$(find "$work/aermap" -type f -iname aermap.f -printf '%h\n' | head -1)"
pushd "$aermap_dir" >/dev/null
aermap_sources=(mod_main1 mod_tifftags aermap sub_calchc sub_chkadj sub_chkext sub_demchk sub_nedchk sub_cnrcnv sub_demrec sub_demsrc sub_domcnv sub_initer_dem sub_initer_ned sub_nadcon sub_reccnv sub_recelv sub_srccnv sub_srcelv sub_utmgeo sub_read_tifftags)
for source in "${aermap_sources[@]}"; do gfortran -m64 -c -fbounds-check -Wuninitialized -static -O2 "${source}.f"; done
gfortran -m64 -static -O2 -o "$runtime/aermap.exe" "${aermap_sources[@]/%/.o}"
popd >/dev/null

cp "$(find "$work/bpip" -type f -iname 'bpipprm.exe' | head -1)" "$runtime/bpipprm.exe"
file "$runtime"/*.exe

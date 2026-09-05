# Nutanix Compatibility Watch

Weekly automated check of the Nutanix Compatibility & Interoperability Matrix
(Platform Compatibility, AHV hypervisor) for:

- **NX-1175S-G8** (Ice Lake)
- **NX-1175S-G10** (Intel Xeon 6505P / Granite Rapids)

Live page: https://eelcoornd.github.io/nutanix-compat-watch/

`check.py` pulls `https://portal.nutanix.com/api/v1/compatibilityMatrixPlatform`
(the public JSON API behind the portal UI — no login needed), finds the
highest AOS version compatible with each platform under AHV, and writes
`data.json` + `index.html`. A GitHub Actions workflow runs this every Monday,
commits the result, and republishes the Pages site. When the latest AOS
version changes since the previous run, the page shows a "NEW" badge and the
commit message says so — so `git log` / GitHub notifications on this repo
double as a changelog.

Run manually: `python3 check.py`

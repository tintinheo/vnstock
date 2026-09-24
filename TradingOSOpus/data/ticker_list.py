"""data/ticker_list.py - Full ticker lists for HOSE, HNX, UPCOM.

Fetches live from KBS API, falls back to hardcoded if API fails.
"""
import requests, logging

logger = logging.getLogger(__name__)

KBS_IIS = "https://kbbuddywts.kbsec.com.vn/iis-server/investment"

def fetch_tickers_live(exchange="HOSE", timeout=10):
    """Fetch ALL tickers from KBS API for an exchange."""
    try:
        url = f"{KBS_IIS}/index/{exchange}/stocks"
        r = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                logger.info(f"[KBS] {exchange}: {len(data)} tickers")
                return sorted([t for t in data if isinstance(t, str)])
    except Exception as e:
        logger.warning(f"[KBS] fetch {exchange} tickers: {e}")
    return []


# Hardcoded comprehensive lists (fallback)
HOSE_TICKERS = sorted(list(set([
    "AAA","AAT","ABR","ABS","ABT","ACB","ACC","ACG","ACL","ADG","ADS",
    "AGG","AGM","AGR","AMD","ANV","APC","APG","APH","ASM","AST",
    "BAF","BBC","BCE","BCG","BCM","BFC","BID","BKG","BMC","BMI",
    "BMP","BRC","BSI","BTT","BVH","BWE","C32","C47","CAV","CCL",
    "CDC","CDO","CEO","CHP","CIG","CII","CLC","CLW","CMG","CMV",
    "CMX","CNG","COM","CRC","CRE","CSC","CSM","CTD","CTF","CTG",
    "CTI","CTR","CVT","D2D","DAH","DAT","DBC","DBD","DCM","DDV",
    "DGC","DGW","DHA","DHC","DHG","DIG","DLG","DMC","DNM","DPG",
    "DPM","DQC","DRC","DSN","DTL","DVN","DVP","DXG","DXS","DXV",
    "E1V","EIB","ELC","EMC","EVE","EVF","EVG","FCN","FDC","FIT",
    "FMC","FPT","FRT","FTS","GAB","GAS","GDT","GEG","GEX","GIL",
    "GMD","GTA","GTN","GVR","HAG","HAH","HAI","HAP","HAS","HAX",
    "HBC","HCD","HCM","HDB","HDC","HDG","HHP","HHS","HHV","HID",
    "HMC","HNG","HOT","HPG","HPX","HQC","HRC","HSG","HT1","HTL",
    "HTN","HTV","HUB","ICT","IDI","IDJ","IJC","IMP","IN4","ITA",
    "ITC","ITD","JVC","KBC","KDC","KDH","KHP","KMR","KOS","KSB",
    "L10","LAF","LBM","LCG","LDG","LEC","LGC","LGL","LHG","LIX",
    "LSS","MCG","MCP","MDG","MHC","MIG","MPT","MSH","MSN","MST",
    "MWG","NAF","NAG","NAV","NBB","NBP","NCT","NDX","NET","NFC",
    "NHH","NHS","NKG","NLG","NNC","NSC","NT2","NTL","NVL","NVT",
    "OGC","OPC","ORS","PAC","PAN","PC1","PDR","PET","PGD","PGI",
    "PGN","PGS","PGV","PHC","PHR","PIT","PJT","PLX","PME","PMG",
    "PNC","PNJ","POM","POW","PPC","PSH","PTB","PTC","PTL","PVD",
    "PVP","PVT","PXS","QBS","QNS","RAL","RDP","REE","ROS","S4A",
    "SAB","SAM","SAV","SBA","SBT","SBV","SC5","SCD","SCR","SCS",
    "SFC","SFG","SFI","SGN","SGP","SGR","SGT","SHA","SHI","SHP",
    "SII","SIP","SJD","SJS","SMA","SMB","SMC","SPM","SRC","SRF",
    "SSC","SSI","ST8","STB","STG","STK","SVC","SVD","SVI","SVT",
    "SZC","TAC","TBC","TCB","TCH","TCL","TCM","TDC","TDG","TDH",
    "TDM","TDP","TDW","TEG","TGG","THG","THI","TIG","TIE","TIP",
    "TIX","TLD","TLG","TLH","TMP","TMS","TMT","TN1","TNH","TNI",
    "TNT","TPC","TPB","TRA","TSC","TTB","TTE","TTF","TV2","TVB",
    "TVS","TVT","TYA","UDC","UIC","VCA","VCB","VCF","VCG","VCI",
    "VCR","VDP","VDS","VFG","VGC","VGP","VHC","VHE","VHM","VIB",
    "VIC","VIP","VIX","VJC","VMD","VND","VNE","VNG","VNL","VNM",
    "VNS","VOS","VPG","VPH","VPI","VPB","VPS","VRC","VRE","VSC",
    "VSH","VSI","VTB","VTO","VTV","YEG",
])))

HNX_TICKERS = sorted(list(set([
    "AAV","AMC","API","APS","ARM","BAB","BBS","BCC","BCF","BDB",
    "BED","BHN","BKC","BNA","BST","BTS","BTW","BVG","BVS","C92",
    "CAG","CAN","CAP","CCR","CDN","CEO","CET","CHP","CJC","CMC",
    "CMI","CMS","CPC","CT3","CT6","CTA","CTB","CTC","CTM","CTS",
    "CVN","DAD","DAE","DCH","DDG","DHB","DHP","DHT","DID","DIH",
    "DL1","DNC","DNP","DP3","DST","DTB","DTC","DTD","DTG","DTH",
    "DTK","DTN","DTV","DVG","DVM","DXP","DZM","GKM","GLT","HAS",
    "HGM","HKB","HLD","HUT","ICG","IDC","IDV","IPA","KBC","KLF",
    "KSF","KSV","KVC","L14","L18","LAS","LHC","LIG","MBS","MCO",
    "MEC","MVB","NBC","NDN","NET","NHA","NRC","NTP","NVB","NVT",
    "OCH","PDB","PHN","PLC","PMB","PRE","PSC","PSD","PTI","PVB",
    "PVC","PVG","PVL","PVS","PVI","S99","SCG","SDG","SDN","SDP",
    "SDT","SEB","SGH","SHN","SHS","SJ1","SLS","SMT","SRA","SSM",
    "TAR","TCS","TDN","TET","TH1","THD","THS","TKC","TKU","TLC",
    "TMB","TNG","TPH","TPP","TTH","TTT","TV1","TV2","TV3","TV4",
    "TVC","TVD","VC1","VC2","VC3","VC5","VC6","VC7","VC9","VCC",
    "VCM","VCS","VDL","VE1","VE2","VE3","VE4","VE8","VE9","VFS",
    "VGS","VHD","VHL","VIF","VIT","VKC","VMI","VNF","VNR","VTC",
    "VTH","VTZ","VTV","VXB","WCS","WSS",
])))

UPCOM_TICKERS = sorted(list(set([
    "AAS","ABB","ABI","ABW","ACE","ACM","ACV","AGF","AMP","APT",
    "BAX","BGM","BHC","BSA","BSR","BTG","CAB","CCA","CCH","CDH",
    "CFM","CGV","CKA","CLH","CLM","CMP","CMN","CNH","CPH","CST",
    "CTN","DAG","LPB","MCH","MPC","OIL","QTP","TCX","VCK","VEA",
    "VGI","VPL","VPX","VTP","SSB",
])))


def get_all_tickers():
    """Get all tickers. Try live API first, fallback to hardcoded."""
    result = {}
    for ex, fallback in [("HOSE", HOSE_TICKERS), ("HNX", HNX_TICKERS), ("UPCOM", UPCOM_TICKERS)]:
        live = fetch_tickers_live(ex)
        result[ex] = live if len(live) > len(fallback) * 0.5 else fallback
    return result


def get_exchange_tickers(exchange):
    """Get tickers for one exchange."""
    mapping = {"HOSE": HOSE_TICKERS, "HNX": HNX_TICKERS, "UPCOM": UPCOM_TICKERS}
    live = fetch_tickers_live(exchange)
    fb = mapping.get(exchange.upper(), [])
    return live if len(live) > len(fb) * 0.5 else fb


def get_ticker_count():
    t = get_all_tickers()
    return {k: len(v) for k, v in t.items()}

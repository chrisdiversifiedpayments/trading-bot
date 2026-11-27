"""Stock lists for fair swing tests.

LARGE_2021: about 100 of the largest US companies as of mid-2021, written down from that time's
market-cap rankings, so it includes later laggards and companies that were bought out or delisted.
Tickers are today's names where a company renamed (FB->META, ANTM->ELV, SQ->XYZ).
SECTOR_FUNDS: index and sector ETFs, which have no "picked the winners" problem.
"""
LARGE_2021 = """AAPL MSFT AMZN GOOGL META TSLA BRK.B NVDA JPM JNJ V UNH HD PG MA DIS PYPL BAC ADBE CMCSA
NFLX XOM CRM VZ KO INTC PFE CSCO PEP T ABT TMO WMT NKE MRK ABBV CVX AVGO ACN COST MCD DHR WFC TXN
QCOM MDT NEE LLY HON BMY UPS LIN ORCL C PM SBUX AMGN UNP LOW INTU MS RTX BA IBM GS BLK AMAT CAT
MMM AMT GE ISRG CVS DE TGT CHTR MO SCHW SPGI ZTS GILD LMT MU NOW ELV BKNG FIS ATVI TWTR MRNA ZM
XYZ SNAP WBA CCI DUK SO MDLZ CL USB PNC TFC""".split()
SECTOR_FUNDS = "SPY QQQ IWM DIA XLK XLF XLE XLV XLY XLP XLI XLU XLB XLRE XLC".split()

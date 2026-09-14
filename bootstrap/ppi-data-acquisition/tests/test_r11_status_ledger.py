from pathlib import Path
import unittest


class R11StatusLedgerTests(unittest.TestCase):
    def test_canonical_status_ledger_remains_fail_closed(self) -> None:
        text = Path(
            "docs/architecture/PPI_R11_BATCH3_R2_REMEDIATION_STATUS.md"
        ).read_text(encoding="utf-8")

        required = (
            "## FINISHED",
            "## REMAINING",
            "MarketMakingLFG/ppi-data-acquisition",
            "1312286476",
            "r11-public-acquisition-protected",
            "8 / 80",
            "2 / 20",
            "QCOM, MRVL, GFS, TXN",
            "automatic registry mutation `disabled`",
            "Implementation completion alone never grants pilot evidence or registry credit.",
        )
        for value in required:
            self.assertIn(value, text)

        self.assertNotIn("spoudel2010-ux/ppi-data-acquisition", text)


if __name__ == "__main__":
    unittest.main()

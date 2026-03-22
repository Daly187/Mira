"""
Affiliate Link Tracking — tracks all affiliate links and reports weekly revenue.

Spec reference: Section 7.4

Mira registers affiliate links across platforms, tracks clicks and conversions,
and generates weekly revenue reports to identify top-performing links.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("mira.modules.affiliate")


class AffiliateTracker:
    """Tracks affiliate links, clicks, conversions, and revenue."""

    def __init__(self, mira):
        self.mira = mira
        self.db = mira.memory.sqlite

    async def initialise(self):
        """Create affiliate_links and affiliate_clicks tables in SQLite."""
        self.db.conn.executescript("""
            CREATE TABLE IF NOT EXISTS affiliate_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                product_name TEXT NOT NULL,
                affiliate_url TEXT NOT NULL,
                original_url TEXT,
                commission_type TEXT DEFAULT 'percentage',
                commission_rate REAL DEFAULT 0.0,
                status TEXT DEFAULT 'active',
                total_clicks INTEGER DEFAULT 0,
                total_conversions INTEGER DEFAULT 0,
                total_revenue REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS affiliate_clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link_id INTEGER NOT NULL,
                source_platform TEXT,
                source_post_id TEXT,
                clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                converted INTEGER DEFAULT 0,
                revenue_amount REAL DEFAULT 0.0,
                order_id TEXT,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (link_id) REFERENCES affiliate_links(id)
            );

            CREATE INDEX IF NOT EXISTS idx_affiliate_links_platform ON affiliate_links(platform);
            CREATE INDEX IF NOT EXISTS idx_affiliate_links_status ON affiliate_links(status);
            CREATE INDEX IF NOT EXISTS idx_affiliate_clicks_link_id ON affiliate_clicks(link_id);
            CREATE INDEX IF NOT EXISTS idx_affiliate_clicks_clicked ON affiliate_clicks(clicked_at);
            CREATE INDEX IF NOT EXISTS idx_affiliate_clicks_converted ON affiliate_clicks(converted);
        """)
        self.db.conn.commit()
        logger.info("Affiliate tracking tables initialised.")

    async def register_link(
        self,
        platform: str,
        product_name: str,
        affiliate_url: str,
        original_url: str = None,
        commission_type: str = "percentage",
        commission_rate: float = 0.0,
        metadata: dict = None,
    ) -> int:
        """Store a new affiliate link. Returns the link ID."""
        cursor = self.db.conn.execute(
            """INSERT INTO affiliate_links
               (platform, product_name, affiliate_url, original_url,
                commission_type, commission_rate, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                platform,
                product_name,
                affiliate_url,
                original_url,
                commission_type,
                commission_rate,
                json.dumps(metadata or {}),
            ),
        )
        self.db.conn.commit()
        link_id = cursor.lastrowid

        self.db.log_action(
            "affiliate",
            "register_link",
            f"Registered {product_name} on {platform}",
            {"link_id": link_id, "platform": platform, "product_name": product_name},
        )
        logger.info(f"Registered affiliate link #{link_id}: {product_name} ({platform})")
        return link_id

    async def track_click(
        self,
        link_id: int,
        source_platform: str = None,
        source_post_id: str = None,
    ) -> int:
        """Log a click on an affiliate link. Returns the click ID."""
        # Verify link exists
        link = self.db.conn.execute(
            "SELECT id FROM affiliate_links WHERE id = ?", (link_id,)
        ).fetchone()
        if not link:
            raise ValueError(f"Affiliate link #{link_id} not found")

        cursor = self.db.conn.execute(
            """INSERT INTO affiliate_clicks (link_id, source_platform, source_post_id)
               VALUES (?, ?, ?)""",
            (link_id, source_platform, source_post_id),
        )
        # Increment total_clicks on the link
        self.db.conn.execute(
            """UPDATE affiliate_links
               SET total_clicks = total_clicks + 1, updated_at = ?
               WHERE id = ?""",
            (datetime.now().isoformat(), link_id),
        )
        self.db.conn.commit()
        return cursor.lastrowid

    async def log_conversion(
        self,
        link_id: int,
        revenue_amount: float,
        order_id: str = None,
    ) -> int:
        """Log an actual conversion/sale with revenue. Returns the click ID updated or created."""
        # Verify link exists
        link = self.db.conn.execute(
            "SELECT id, product_name, platform FROM affiliate_links WHERE id = ?", (link_id,)
        ).fetchone()
        if not link:
            raise ValueError(f"Affiliate link #{link_id} not found")

        # Find the most recent unconverted click for this link, or create a new entry
        recent_click = self.db.conn.execute(
            """SELECT id FROM affiliate_clicks
               WHERE link_id = ? AND converted = 0
               ORDER BY clicked_at DESC LIMIT 1""",
            (link_id,),
        ).fetchone()

        if recent_click:
            click_id = recent_click["id"]
            self.db.conn.execute(
                """UPDATE affiliate_clicks
                   SET converted = 1, revenue_amount = ?, order_id = ?
                   WHERE id = ?""",
                (revenue_amount, order_id, click_id),
            )
        else:
            # No unconverted click — create a direct conversion entry
            cursor = self.db.conn.execute(
                """INSERT INTO affiliate_clicks
                   (link_id, converted, revenue_amount, order_id)
                   VALUES (?, 1, ?, ?)""",
                (link_id, revenue_amount, order_id),
            )
            click_id = cursor.lastrowid

        # Update link totals
        self.db.conn.execute(
            """UPDATE affiliate_links
               SET total_conversions = total_conversions + 1,
                   total_revenue = total_revenue + ?,
                   updated_at = ?
               WHERE id = ?""",
            (revenue_amount, datetime.now().isoformat(), link_id),
        )
        self.db.conn.commit()

        self.db.log_action(
            "affiliate",
            "conversion",
            f"${revenue_amount:.2f} from {dict(link)['product_name']}",
            {
                "link_id": link_id,
                "revenue": revenue_amount,
                "order_id": order_id,
                "platform": dict(link)["platform"],
            },
        )
        # Also log to earning revenue for the earnings dashboard
        self.db.log_action(
            "earning_content",
            "revenue",
            str(revenue_amount),
            {"source": "affiliate", "link_id": link_id, "order_id": order_id},
        )

        logger.info(f"Conversion on link #{link_id}: ${revenue_amount:.2f} (order: {order_id})")
        return click_id

    async def get_weekly_report(self) -> dict:
        """Generate weekly affiliate revenue report."""
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()

        # Total clicks this week
        clicks_row = self.db.conn.execute(
            """SELECT COUNT(*) as total_clicks
               FROM affiliate_clicks
               WHERE clicked_at >= ?""",
            (seven_days_ago,),
        ).fetchone()

        # Total conversions and revenue this week
        conv_row = self.db.conn.execute(
            """SELECT COUNT(*) as total_conversions,
                      COALESCE(SUM(revenue_amount), 0) as total_revenue
               FROM affiliate_clicks
               WHERE clicked_at >= ? AND converted = 1""",
            (seven_days_ago,),
        ).fetchone()

        # Per-platform breakdown
        platform_rows = self.db.conn.execute(
            """SELECT al.platform,
                      COUNT(ac.id) as clicks,
                      SUM(CASE WHEN ac.converted = 1 THEN 1 ELSE 0 END) as conversions,
                      COALESCE(SUM(ac.revenue_amount), 0) as revenue
               FROM affiliate_clicks ac
               JOIN affiliate_links al ON ac.link_id = al.id
               WHERE ac.clicked_at >= ?
               GROUP BY al.platform
               ORDER BY revenue DESC""",
            (seven_days_ago,),
        ).fetchall()

        # Per-link breakdown (top performers this week)
        link_rows = self.db.conn.execute(
            """SELECT al.id, al.product_name, al.platform,
                      COUNT(ac.id) as clicks,
                      SUM(CASE WHEN ac.converted = 1 THEN 1 ELSE 0 END) as conversions,
                      COALESCE(SUM(ac.revenue_amount), 0) as revenue
               FROM affiliate_clicks ac
               JOIN affiliate_links al ON ac.link_id = al.id
               WHERE ac.clicked_at >= ?
               GROUP BY al.id
               ORDER BY revenue DESC
               LIMIT 10""",
            (seven_days_ago,),
        ).fetchall()

        total_clicks = clicks_row["total_clicks"] if clicks_row else 0
        total_conversions = conv_row["total_conversions"] if conv_row else 0
        total_revenue = conv_row["total_revenue"] if conv_row else 0.0
        conversion_rate = (
            (total_conversions / total_clicks * 100) if total_clicks > 0 else 0.0
        )

        return {
            "period": "last_7_days",
            "period_start": seven_days_ago,
            "period_end": datetime.now().isoformat(),
            "total_clicks": total_clicks,
            "total_conversions": total_conversions,
            "total_revenue": round(total_revenue, 2),
            "conversion_rate": round(conversion_rate, 2),
            "by_platform": [dict(r) for r in platform_rows],
            "top_links": [dict(r) for r in link_rows],
        }

    async def get_all_links(self) -> list[dict]:
        """List all registered affiliate links with stats."""
        rows = self.db.conn.execute(
            """SELECT * FROM affiliate_links
               ORDER BY total_revenue DESC, total_clicks DESC"""
        ).fetchall()
        return [dict(row) for row in rows]

    async def get_top_performers(self, period: str = "month") -> list[dict]:
        """Identify best-performing affiliate links for a given period."""
        if period == "week":
            since = (datetime.now() - timedelta(days=7)).isoformat()
        elif period == "month":
            since = (datetime.now() - timedelta(days=30)).isoformat()
        elif period == "quarter":
            since = (datetime.now() - timedelta(days=90)).isoformat()
        elif period == "year":
            since = (datetime.now() - timedelta(days=365)).isoformat()
        else:
            since = (datetime.now() - timedelta(days=30)).isoformat()

        rows = self.db.conn.execute(
            """SELECT al.id, al.platform, al.product_name, al.affiliate_url,
                      al.commission_type, al.commission_rate,
                      COUNT(ac.id) as period_clicks,
                      SUM(CASE WHEN ac.converted = 1 THEN 1 ELSE 0 END) as period_conversions,
                      COALESCE(SUM(ac.revenue_amount), 0) as period_revenue,
                      al.total_clicks, al.total_conversions, al.total_revenue
               FROM affiliate_links al
               LEFT JOIN affiliate_clicks ac
                   ON ac.link_id = al.id AND ac.clicked_at >= ?
               WHERE al.status = 'active'
               GROUP BY al.id
               ORDER BY period_revenue DESC, period_clicks DESC
               LIMIT 20""",
            (since,),
        ).fetchall()

        results = []
        for row in rows:
            r = dict(row)
            r["period"] = period
            r["conversion_rate"] = (
                round(r["period_conversions"] / r["period_clicks"] * 100, 2)
                if r["period_clicks"] > 0
                else 0.0
            )
            results.append(r)

        return results

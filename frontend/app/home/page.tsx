"use client";
import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Bot,
  TrendingUp,
  TrendingDown,
  Activity,
  Wallet,
  Plus,
  ChevronRight,
  Loader2,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

// ===== Types =====
interface TradeOut {
  id: number;
  bot_id: string;
  pair: string;
  direction: string;
  open_rate: number;
  close_rate: number | null;
  profit_usdt: number | null;
  profit_pct: number | null;
  exit_reason: string | null;
  open_time: string;
  close_time: string | null;
}

interface HomeStats {
  service_balance: number;
  total_profit: number;
  bots_running: number;
  bots_total: number;
  recent_trades: TradeOut[];
}

// ===== Helpers =====
const formatUsdt = (v: number, showSign = true): string => {
  const sign = showSign && v >= 0 ? "+" : "";
  return `${sign}$${Math.abs(v).toFixed(2)}`;
};

const formatPct = (v: number): string =>
  `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

const formatDate = (iso: string | null): string => {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${d.getDate().toString().padStart(2, "0")}.${(d.getMonth() + 1)
    .toString()
    .padStart(2, "0")} ${d.getHours().toString().padStart(2, "0")}:${d
    .getMinutes()
    .toString()
    .padStart(2, "0")}`;
};

// ===== Component =====
export default function HomePage() {
  const router = useRouter();
  const [stats, setStats] = useState<HomeStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch("/stats/home")
      .then((data: HomeStats) => setStats(data))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const profitColor = (stats?.total_profit ?? 0) >= 0 ? "#10b981" : "#ef4444";

  return (
    <div style={styles.page}>
      {/* ── Header ── */}
      <header style={styles.header}>
        <div style={styles.headerLogo}>
          <div style={styles.logoIcon}>
            <Bot size={16} color="#fff" />
          </div>
          <span style={styles.logoText}>CryptoBot</span>
        </div>
        <nav style={styles.headerNav}>
          <Link href="/stats" style={styles.navLink}>
            Статистика
          </Link>
          <button
            style={styles.newBotBtn}
            onClick={() => router.push("/bot-creation")}
          >
            <Plus size={14} />
            Новый бот
          </button>
        </nav>
      </header>

      <main style={styles.main}>
        {/* Loading */}
        {loading && (
          <div style={styles.centered}>
            <Loader2 size={18} style={{ animation: "spin 1s linear infinite", color: "#6b7280" }} />
            <span style={{ color: "#6b7280", marginLeft: 10 }}>Загрузка…</span>
          </div>
        )}

        {/* Error */}
        {!loading && error && (
          <div style={{ color: "#ef4444", padding: "20px 0" }}>{error}</div>
        )}

        {/* Content */}
        {!loading && !error && stats && (
          <>
            {/* ── Summary cards ── */}
            <div style={styles.cardsGrid}>
              {/* Total P&L */}
              <div style={styles.card}>
                <div style={styles.cardIcon("#10b981")}>
                  {stats.total_profit >= 0
                    ? <TrendingUp size={16} color="#10b981" />
                    : <TrendingDown size={16} color="#ef4444" />}
                </div>
                <div>
                  <div style={styles.cardLabel}>Общий P&L</div>
                  <div style={{ ...styles.cardValue, color: profitColor }}>
                    {formatUsdt(stats.total_profit)}
                  </div>
                </div>
              </div>

              {/* Service balance */}
              <div style={styles.card}>
                <div style={styles.cardIcon("#3b82f6")}>
                  <Wallet size={16} color="#60a5fa" />
                </div>
                <div>
                  <div style={styles.cardLabel}>Баланс сервиса</div>
                  <div style={{ ...styles.cardValue, color: "#e4e7f0" }}>
                    {formatUsdt(stats.service_balance, false)}
                  </div>
                </div>
              </div>

              {/* Active bots */}
              <div style={styles.card}>
                <div style={styles.cardIcon("#6366f1")}>
                  <Activity size={16} color="#818cf8" />
                </div>
                <div>
                  <div style={styles.cardLabel}>Активных ботов</div>
                  <div style={{ ...styles.cardValue, color: "#e4e7f0" }}>
                    {stats.bots_running}
                    <span style={styles.cardSub}> / {stats.bots_total}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* ── Recent trades ── */}
            <div style={styles.section}>
              <div style={styles.sectionHead}>
                <span style={styles.sectionTitle}>Последние сделки</span>
                <Link href="/stats" style={styles.seeAll}>
                  Все <ChevronRight size={12} style={{ verticalAlign: "middle" }} />
                </Link>
              </div>

              {stats.recent_trades.length === 0 ? (
                <div style={styles.empty}>Сделок пока нет — запустите бота!</div>
              ) : (
                <div style={styles.tradeList}>
                  {stats.recent_trades.map((t) => (
                    <div key={t.id} style={styles.tradeRow}>
                      {/* Direction badge */}
                      <span
                        style={{
                          ...styles.badge,
                          background: t.direction === "long"
                            ? "rgba(16,185,129,0.15)"
                            : "rgba(239,68,68,0.15)",
                          color: t.direction === "long" ? "#10b981" : "#ef4444",
                        }}
                      >
                        {t.direction === "long" ? "Long" : "Short"}
                      </span>

                      {/* Pair */}
                      <span style={styles.tradePair}>{t.pair}</span>

                      {/* Exit reason */}
                      {t.exit_reason && (
                        <span style={styles.exitReason}>{t.exit_reason}</span>
                      )}

                      {/* Spacer */}
                      <span style={{ flex: 1 }} />

                      {/* P&L */}
                      <span
                        style={{
                          fontWeight: 700,
                          fontSize: 13,
                          color: (t.profit_usdt ?? 0) >= 0 ? "#10b981" : "#ef4444",
                          marginRight: 12,
                        }}
                      >
                        {t.profit_usdt != null ? formatUsdt(t.profit_usdt) : "—"}
                      </span>

                      {t.profit_pct != null && (
                        <span
                          style={{
                            fontSize: 11,
                            color: t.profit_pct >= 0 ? "#10b981" : "#ef4444",
                            marginRight: 14,
                            minWidth: 52,
                            textAlign: "right",
                          }}
                        >
                          {formatPct(t.profit_pct)}
                        </span>
                      )}

                      {/* Date */}
                      <span style={styles.tradeDate}>{formatDate(t.close_time)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* ── Quick actions ── */}
            <div style={styles.actions}>
              <button
                style={styles.primaryBtn}
                onClick={() => router.push("/bot-creation")}
              >
                <Plus size={15} />
                Создать нового бота
              </button>
              <Link href="/stats" style={styles.secondaryBtn}>
                Подробная статистика
              </Link>
            </div>
          </>
        )}
      </main>

      <style jsx global>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0b1220; }
      `}</style>
    </div>
  );
}

// ===== Styles =====
const styles = {
  page: {
    minHeight: "100vh",
    background: "#0b1220",
    color: "#e4e7f0",
    fontFamily: "'Inter', system-ui, sans-serif",
    fontSize: 13,
  } as React.CSSProperties,

  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "16px 32px",
    borderBottom: "1px solid rgba(255,255,255,0.06)",
    background: "#0f1729",
  } as React.CSSProperties,

  headerLogo: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  } as React.CSSProperties,

  logoIcon: {
    width: 28,
    height: 28,
    borderRadius: 8,
    background: "linear-gradient(135deg,#3b82f6,#2563eb)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  } as React.CSSProperties,

  logoText: {
    fontSize: 16,
    fontWeight: 700,
    color: "#e4e7f0",
  } as React.CSSProperties,

  headerNav: {
    display: "flex",
    alignItems: "center",
    gap: 16,
  } as React.CSSProperties,

  navLink: {
    color: "#9ca3af",
    textDecoration: "none",
    fontSize: 13,
    fontWeight: 500,
    transition: "color 0.15s",
  } as React.CSSProperties,

  newBotBtn: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "7px 14px",
    borderRadius: 9,
    border: "none",
    background: "linear-gradient(135deg,#3b82f6,#2563eb)",
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
  } as React.CSSProperties,

  main: {
    maxWidth: 900,
    margin: "0 auto",
    padding: "36px 24px",
    display: "flex",
    flexDirection: "column" as const,
    gap: 28,
  } as React.CSSProperties,

  centered: {
    display: "flex",
    alignItems: "center",
    padding: "60px 0",
  } as React.CSSProperties,

  cardsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(3, 1fr)",
    gap: 14,
  } as React.CSSProperties,

  card: {
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.07)",
    borderRadius: 14,
    padding: "18px 20px",
    display: "flex",
    alignItems: "center",
    gap: 14,
  } as React.CSSProperties,

  cardIcon: (bg: string) => ({
    width: 38,
    height: 38,
    borderRadius: 10,
    background: bg + "22",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  }) as React.CSSProperties,

  cardLabel: {
    fontSize: 11,
    color: "#6b7280",
    textTransform: "uppercase" as const,
    letterSpacing: "0.5px",
    marginBottom: 5,
  } as React.CSSProperties,

  cardValue: {
    fontSize: 22,
    fontWeight: 700,
    lineHeight: 1,
  } as React.CSSProperties,

  cardSub: {
    fontSize: 14,
    fontWeight: 500,
    color: "#6b7280",
  } as React.CSSProperties,

  section: {
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.07)",
    borderRadius: 14,
    padding: 20,
  } as React.CSSProperties,

  sectionHead: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 16,
  } as React.CSSProperties,

  sectionTitle: {
    fontSize: 13,
    fontWeight: 600,
    color: "#e4e7f0",
  } as React.CSSProperties,

  seeAll: {
    fontSize: 12,
    color: "#60a5fa",
    textDecoration: "none",
    display: "flex",
    alignItems: "center",
    gap: 2,
  } as React.CSSProperties,

  tradeList: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 2,
  } as React.CSSProperties,

  tradeRow: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "10px 4px",
    borderTop: "1px solid rgba(255,255,255,0.04)",
  } as React.CSSProperties,

  badge: {
    padding: "3px 9px",
    borderRadius: 6,
    fontSize: 11,
    fontWeight: 700,
    flexShrink: 0,
  } as React.CSSProperties,

  tradePair: {
    fontWeight: 600,
    color: "#e4e7f0",
    fontSize: 13,
  } as React.CSSProperties,

  exitReason: {
    fontSize: 11,
    color: "#6b7280",
    background: "rgba(255,255,255,0.05)",
    padding: "2px 7px",
    borderRadius: 5,
  } as React.CSSProperties,

  tradeDate: {
    fontSize: 11,
    color: "#4b5563",
    flexShrink: 0,
  } as React.CSSProperties,

  empty: {
    padding: "30px 0",
    textAlign: "center" as const,
    color: "#6b7280",
    fontSize: 13,
  } as React.CSSProperties,

  actions: {
    display: "flex",
    gap: 12,
  } as React.CSSProperties,

  primaryBtn: {
    display: "flex",
    alignItems: "center",
    gap: 7,
    padding: "10px 20px",
    borderRadius: 10,
    border: "none",
    background: "linear-gradient(135deg,#3b82f6,#2563eb)",
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
  } as React.CSSProperties,

  secondaryBtn: {
    display: "flex",
    alignItems: "center",
    padding: "10px 20px",
    borderRadius: 10,
    border: "1px solid rgba(255,255,255,0.1)",
    background: "transparent",
    color: "#9ca3af",
    fontSize: 13,
    fontWeight: 500,
    textDecoration: "none",
  } as React.CSSProperties,
};
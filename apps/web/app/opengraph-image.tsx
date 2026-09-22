import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "#f5f6f5",
          fontFamily: "sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            width: 140,
            height: 140,
            borderRadius: 28,
            alignItems: "center",
            justifyContent: "center",
            background: "#1f2429",
            color: "#ffffff",
            fontSize: 84,
            fontWeight: 700,
          }}
        >
          K
        </div>
        <div style={{ marginTop: 36, fontSize: 56, fontWeight: 600, color: "#1f2429" }}>Koya Lead Agent</div>
        <div style={{ marginTop: 12, fontSize: 28, color: "#5c646c" }}>AI Lead Research &amp; Outreach</div>
      </div>
    ),
    { ...size }
  );
}

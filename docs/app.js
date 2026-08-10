const repository = "kimNarr/SynapCap";
const releaseBase = `https://github.com/${repository}/releases/latest/download`;
const releasePage = `https://github.com/${repository}/releases/latest`;

const assets = {
  windows: "SynapCap-Windows-x64-Setup.exe",
  macArm: "SynapCap-macOS-arm64.dmg",
  macIntel: "SynapCap-macOS-x64.dmg",
};

function detectPlatform() {
  const value = `${navigator.userAgent} ${navigator.platform}`.toLowerCase();
  if (value.includes("win")) return "windows";
  if (value.includes("mac")) return "mac";
  return "other";
}

function configurePrimaryDownload() {
  const platform = detectPlatform();
  const button = document.querySelector("#primary-download");
  const label = document.querySelector("#primary-platform");

  if (platform === "windows") {
    button.href = `${releaseBase}/${assets.windows}`;
    label.textContent = "Windows 10/11 · 64비트";
    document.querySelector('[data-platform-card="windows"]').classList.add("recommended");
  } else if (platform === "mac") {
    button.href = `${releaseBase}/${assets.macArm}`;
    label.textContent = "macOS · Apple Silicon";
    document.querySelector('[data-platform-card="mac"]').classList.add("recommended");
  } else {
    button.href = "#download";
    label.textContent = "Windows 및 macOS";
  }
}

async function loadLatestRelease() {
  const status = document.querySelector("#release-status");
  const meta = document.querySelector("#release-meta");
  try {
    const response = await fetch(`https://api.github.com/repos/${repository}/releases/latest`, {
      headers: { Accept: "application/vnd.github+json" },
    });
    if (!response.ok) throw new Error(`GitHub API ${response.status}`);
    const release = await response.json();
    const published = new Intl.DateTimeFormat("ko-KR", {
      year: "numeric",
      month: "long",
      day: "numeric",
    }).format(new Date(release.published_at));
    const downloads = (release.assets || []).reduce((sum, item) => sum + (item.download_count || 0), 0);

    status.textContent = `${release.tag_name} 다운로드 가능`;
    meta.textContent = `최신 ${release.tag_name} · ${published} 공개 · 누적 다운로드 ${downloads.toLocaleString("ko-KR")}회`;

    const availableAssets = new Map((release.assets || []).map((item) => [item.name, item.browser_download_url]));
    document.querySelectorAll("[data-asset]").forEach((link) => {
      const url = availableAssets.get(link.dataset.asset);
      link.href = url || release.html_url || releasePage;
    });
  } catch (error) {
    status.textContent = "첫 공개 버전 준비 중";
    meta.textContent = "첫 번째 GitHub Release가 게시되면 자동으로 최신 버전이 연결됩니다.";
  }
}

configurePrimaryDownload();
loadLatestRelease();


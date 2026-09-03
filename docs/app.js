const repository = "kimNarr/SynapCap";
const releaseBase = `https://github.com/${repository}/releases/latest/download`;
const releasePage = `https://github.com/${repository}/releases/latest`;

const assets = {
  windows: "SynapCap-Windows-x64-Setup.exe",
  macArm: "SynapCap-macOS-arm64.dmg",
  macIntel: "SynapCap-macOS-x64.dmg",
};

function configureThemeToggle() {
  const toggle = document.querySelector("#theme-toggle");
  const themeMeta = document.querySelector('meta[name="theme-color"]');
  if (!toggle) return;

  const applyTheme = (theme) => {
    const isLight = theme === "light";
    document.documentElement.dataset.theme = theme;
    toggle.setAttribute("aria-pressed", String(isLight));
    toggle.setAttribute("aria-label", isLight ? "다크 테마로 전환" : "라이트 테마로 전환");
    toggle.firstElementChild.textContent = isLight ? "◐" : "☼";
    if (themeMeta) themeMeta.content = isLight ? "#f6f8fc" : "#11111b";
  };

  applyTheme(document.documentElement.dataset.theme || "dark");
  toggle.addEventListener("click", () => {
    const nextTheme = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    localStorage.setItem("synapcap-theme", nextTheme);
    applyTheme(nextTheme);
  });
}

function detectPlatform() {
  const value = `${navigator.userAgent} ${navigator.platform}`.toLowerCase();
  if (value.includes("win")) return "windows";
  if (value.includes("mac")) return "mac";
  return "other";
}

function configurePrimaryDownload() {
  const platform = detectPlatform();
  const button = document.querySelector("#primary-download");
  const buttonTitle = document.querySelector("#primary-download-label");
  const label = document.querySelector("#primary-platform");
  const alternate = document.querySelector("#alternate-download");

  if (platform === "windows") {
    button.href = `${releaseBase}/${assets.windows}`;
    button.dataset.asset = assets.windows;
    buttonTitle.textContent = "Windows 최신 버전";
    label.textContent = "Windows 10/11 · 64비트";
    alternate.href = "#download";
    delete alternate.dataset.asset;
    alternate.textContent = "macOS 버전 선택";
    document.querySelector('[data-platform-card="windows"]').classList.add("recommended");
  } else if (platform === "mac") {
    button.href = "#download";
    delete button.dataset.asset;
    buttonTitle.textContent = "macOS 버전 선택";
    label.textContent = "macOS · Apple Silicon 또는 Intel 선택";
    alternate.href = `${releaseBase}/${assets.windows}`;
    alternate.dataset.asset = assets.windows;
    alternate.textContent = "Windows 최신 버전";
  } else {
    button.href = "#download";
    delete button.dataset.asset;
    buttonTitle.textContent = "설치 파일 선택";
    label.textContent = "Windows 및 macOS";
    alternate.href = `https://github.com/${repository}`;
    delete alternate.dataset.asset;
    alternate.textContent = "소스 보기";
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
    status.textContent = "최신 공개 버전 확인 중";
    meta.textContent = "버전 정보를 불러오지 못했습니다. GitHub Release에서 최신 파일을 확인할 수 있습니다.";
  }
}

configurePrimaryDownload();
configureThemeToggle();
loadLatestRelease();

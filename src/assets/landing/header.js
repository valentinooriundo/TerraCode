(() => {
  const header = document.querySelector("[data-site-header]");
  const videoTitle = document.querySelector("#video-title");
  if (!header || !videoTitle) return;

  function updateHeader() {
    const height = header.offsetHeight;
    document.documentElement.style.setProperty("--header-height", `${height}px`);
    const titleTop = videoTitle.getBoundingClientRect().top;
    header.classList.toggle("show-divider", titleTop <= height + 16);
  }

  addEventListener("scroll", updateHeader, { passive: true });
  addEventListener("resize", updateHeader);
  new ResizeObserver(updateHeader).observe(header);
  updateHeader();
})();

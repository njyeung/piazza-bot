// Piazza AI Assistant - Content Script
// Detects the current post ID from the URL

function extractPostIdFromUrl() {
  // Piazza URLs look like: https://piazza.com/class/merk8zm4in1ib/post/940
  const url = window.location.href;

  // Extract from /post/940 format
  const postMatch = url.match(/\/post\/(\d+)/);
  if (postMatch) {
    return parseInt(postMatch[1], 10);
  }

  return null;
}

function checkCurrentPost() {
  const postId = extractPostIdFromUrl();

  if (postId) {
    console.log(`[Piazza AI] Current post ID: ${postId}`);
  } else {
    console.log('[Piazza AI] Not viewing a specific post');
  }
}

// Check immediately when script loads
checkCurrentPost();

// Listen for URL changes (Piazza is a single-page app)
let lastUrl = window.location.href;
const urlObserver = new MutationObserver(() => {
  const currentUrl = window.location.href;
  if (currentUrl !== lastUrl) {
    lastUrl = currentUrl;
    console.log('[Piazza AI] URL changed, checking post...');
    checkCurrentPost();
  }
});

// Observe the document for changes
urlObserver.observe(document.body, {
  childList: true,
  subtree: true
});

// Also listen to popstate events (back/forward buttons)
window.addEventListener('popstate', () => {
  console.log('[Piazza AI] Navigation detected (popstate)');
  checkCurrentPost();
});

// Also listen to hashchange events
window.addEventListener('hashchange', () => {
  console.log('[Piazza AI] Hash changed');
  checkCurrentPost();
});

console.log('[Piazza AI] Extension loaded and monitoring for post changes');

// ============================================
// RATTLE - Shared JavaScript helpers
// ============================================
// Page-specific functions (viewToken, refreshToken, deleteCampaign,
// generateQR, copyField, ...) are defined inside each template's
// extra_js block, which loads AFTER this file. Keeping them OUT of
// here avoids two different versions of the same function fighting
// each other, and removes the fragile trick of embedding raw JSON
// inside an onclick='...' string.

console.log('RATTLE loaded');

// Escape a string so it is safe to place inside HTML.
function escapeHtml(str) {
    return String(str).replace(/[&<>"]/g, function (m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        if (m === '"') return '&quot;';
        return m;
    });
}

// Copy text to the clipboard, with a fallback for older browsers.
function copyToClipboard(text) {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () {
            console.log('Copied to clipboard');
        }).catch(function () {
            fallbackCopy(text);
        });
    } else {
        fallbackCopy(text);
    }
}

function fallbackCopy(text) {
    var textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    try {
        document.execCommand('copy');
    } catch (e) {
        console.warn('Copy failed - please copy manually.');
    }
    document.body.removeChild(textarea);
}

document.addEventListener('DOMContentLoaded', function () {
    console.log('RATTLE ready');
});

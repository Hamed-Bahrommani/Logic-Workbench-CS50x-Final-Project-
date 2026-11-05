// The symbol buttons need JavaScript, so they are hidden in the HTML and shown
// here. Without JavaScript the forms still work: ASCII spellings (~ & | -> <->)
// can be typed instead. Pages with several inputs (equivalence, argument) insert
// into whichever formula box was focused last.
document.addEventListener("DOMContentLoaded", () => {
        // Copy the current shareable result URL.
    document.querySelectorAll("[data-copy-link]").forEach((button) => {
        const status = button.parentElement.querySelector(".copy-status");

        button.addEventListener("click", async () => {
            try {
                if (navigator.clipboard && window.isSecureContext) {
                    await navigator.clipboard.writeText(window.location.href);
                } else {
                    const temporary = document.createElement("textarea");
                    temporary.value = window.location.href;
                    temporary.style.position = "fixed";
                    temporary.style.opacity = "0";
                    document.body.appendChild(temporary);
                    temporary.select();

                    const copied = document.execCommand("copy");
                    temporary.remove();

                    if (!copied) {
                        throw new Error("Clipboard access unavailable");
                    }
                }

                button.textContent = "Copied!";
                status.textContent = "Result link copied to clipboard.";
            } catch {
                status.textContent = "Unable to copy. You can copy the URL from your address bar.";
            }
        });
    });
    const palette = document.getElementById("symbols");
    const inputs = Array.from(document.querySelectorAll(".formula-input"));
    if (!palette || inputs.length === 0) {
        return;
    }

    let target = inputs[0];
    inputs.forEach((input) => {
        input.addEventListener("focus", () => {
            target = input;
        });
    });

    palette.hidden = false;
    palette.querySelectorAll("[data-insert]").forEach((button) => {
        button.addEventListener("click", () => {
            // Replace the selection (or insert at the caret) and leave the
            // caret just after the new text.
            target.setRangeText(button.dataset.insert, target.selectionStart, target.selectionEnd, "end");
            target.focus();
        });
    });
});
document.getElementById("judgeForm").addEventListener("submit", function (e) {
    e.preventDefault();
    const judgeId = document.getElementById("judgeId").value.trim();
    if (judgeId) {
      window.location.href = "/" + encodeURIComponent(judgeId);
    }
  });
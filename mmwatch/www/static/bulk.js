function getCheckedObjects(which) {
  var result = [];
  var checks = document.getElementsByClassName('obj_check');
  for (var i = 0; i < checks.length; i++) {
    if (checks[i].checked)
      result.push(checks[i].value.split(',')[which]);
    checks[i].checked = false;
  }
  return result;
}

function btnClear() {
  getCheckedObjects(0);
  window.scrollTo(0, 0);
}

function btnLevel0() {
  var checks = getCheckedObjects(0);
  var param = checks.join(',');
  var w = window.open('http://level0.osmz.ru/?url=' + param, '_blank');
  w.focus();
}

function btnRevert(url) {
  var checks = getCheckedObjects(1);
  var param = checks.join(',');
  window.location.assign(url + '?objects=' + param);
}

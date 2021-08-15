$(document).ready(function () {
});

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie != '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            if (cookie.substring(0, name.length + 1) == (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

$.ajaxSetup({
    beforeSend: function(xhr, settings) {
        if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
            xhr.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
        }
    }
});

function customSave(){
	 console.log("called")
	 var password = $("#inputPassword").val()
	 console.log(password)
	 var resetString = $("#resetstring-hidden").val()

	 var data = {'password': password}
	 console.log(data)
	 alert(password)

	  // $.ajax({
   //        method :"POST",
   //        url: "/password/reset/"+resetString,
   //        cache: false,
   //        data: JSON.stringify(data),
   //        contentType: "application/json; charset=UTF-8",
   //        dataType: "json",
   //        success: function (data) {

   //          if(data['status'] == 'success'){
   //            $("#resultlabel").text = "Password changed successfully"
   //          }else{
   //            $("#resultlabel").text = "Password could not be changed"
   //          }
   //        },
   //        error: function (data) {
   //        	   $("#resultlabel").text = "Password could not be changed"
   //        }
   //      });
  }
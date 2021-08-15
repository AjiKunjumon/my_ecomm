jQuery(document).ready(function() {

$("#twitter-share").on("click", function(e) {
	var text       = jQuery(this).data('easyshare-tweet-text') || '';
	var width      = 575;
	var height     = 440;
	var leftOffset = (jQuery(window).width() - width) / 2;
	var topOffset  = (jQuery(window).height() - height) / 2;
	var url        = 'https://twitter.com/share?text=' + encodeURIComponent(text);
	var opts       = 'status=1,width=' + width + ',height=' + height + ',top=' + topOffset + ',left=' + leftOffset;

	window.open(url, 'twitter', opts);
});

});
<?php

//$postdata = http_build_query($_REQUEST, '&', PHP_QUERY_RFC3986); // Does not work - php 5.3 
$kv = array();
foreach ($_REQUEST as $key => $value) {
    $kv[] = "$key=".rawurlencode($value);
}
$mypostdata = join("&", $kv);

$opts = array('http' =>
    array(
        'method'  => 'POST',
        'header' => array('Content-Type: application/x-www-form-urlencoded; charset=UTF-8', 
        	'Pragma: no-cache',
        	'Accept: */*',
        	'Content-Length:'.strlen($mypostdata)),
        'content' => $mypostdata
    )
);

$context  = stream_context_create($opts);
$result = file_get_contents($addr, false, $context);

echo $result;

?>
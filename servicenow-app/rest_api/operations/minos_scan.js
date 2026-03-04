(function process(/*RESTAPIRequest*/ request, /*RESTAPIResponse*/ response) {
    var scanner = new MinosScanner();
    var result = scanner.scan();

    response.setStatus(200);
    response.setBody(result);
})(request, response);

import Toybox.Communications;
import Toybox.Lang;

//! Talks to the relay through the phone (Garmin Connect Mobile proxy). HTTPS only.
class RelayClient {
    private var _base as String;
    private var _token as String;

    public function initialize() {
        _base = Secrets.RELAY_URL;
        _token = Secrets.RELAY_TOKEN;
    }

    //! GET /pending (description cut to 240 chars for the small screen)
    public function fetchPending(callback as Method(code as Number, data as Dictionary or String or Null) as Void) as Void {
        var options = {
            :method => Communications.HTTP_REQUEST_METHOD_GET,
            :headers => {"Authorization" => "Bearer " + _token},
            :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
        };
        Communications.makeWebRequest(_base + "/pending", {"max_desc" => 240}, options, callback);
    }

    //! POST /answer/{id} with {"index": n}
    public function sendAnswer(id as String, index as Number, callback as Method(code as Number, data as Dictionary or String or Null) as Void) as Void {
        var options = {
            :method => Communications.HTTP_REQUEST_METHOD_POST,
            :headers => {
                "Authorization" => "Bearer " + _token,
                "Content-Type" => Communications.REQUEST_CONTENT_TYPE_JSON
            },
            :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
        };
        Communications.makeWebRequest(_base + "/answer/" + id, {"index" => index}, options, callback);
    }

    //! Short German text for a response code (codes from the Communications docs, 401/409 from the relay)
    public static function describe(code as Number) as String {
        if (code == 401) {
            return "Token falsch";
        } else if (code == 409) {
            return "Schon beantwortet\noder abgelaufen";
        } else if (code == -104 || code == -1) {
            return "Handy nicht\nverbunden";
        } else if (code == -1001) {
            return "HTTPS noetig";
        } else if (code == -300 || code == -2 || code == -3) {
            return "Zeitueberschreitung";
        } else if (code == -402) {
            return "Antwort zu gross";
        }
        return "Fehler " + code.toString();
    }
}

import Toybox.Attention;
import Toybox.Graphics;
import Toybox.Lang;
import Toybox.Timer;
import Toybox.WatchUi;

//! Main screen: polls the relay while the app is open and shows the pending question.
class MainView extends WatchUi.View {
    private const POLL_MS = 4000;

    private var _client as RelayClient;
    private var _timer as Timer.Timer?;
    private var _busy as Boolean = false;
    private var _pending as Dictionary?;
    private var _shownId as String?;
    private var _answeredId as String?;
    private var _status as String = "Verbinde...";

    public function initialize() {
        View.initialize();
        _client = new RelayClient();
    }

    public function onShow() as Void {
        var timer = new Timer.Timer();
        timer.start(method(:poll), POLL_MS, true);
        _timer = timer;
        poll();
    }

    public function onHide() as Void {
        var timer = _timer;
        if (timer != null) {
            timer.stop();
        }
        _timer = null;
    }

    //! Timer callback
    public function poll() as Void {
        if (_busy) {
            return;
        }
        _busy = true;
        _client.fetchPending(method(:onPending));
    }

    public function onPending(code as Number, data as Dictionary or String or Null) as Void {
        _busy = false;
        if (code == 200 && data instanceof Dictionary) {
            var item = data["pending"];
            if (item instanceof Dictionary && !(item["id"] as String).equals(_answeredId)) {
                _pending = item;
                var id = item["id"] as String;
                if (!id.equals(_shownId)) {  // new question: nudge once
                    _shownId = id;
                    if (Attention has :vibrate) {
                        Attention.vibrate([new Attention.VibeProfile(75, 500)]);
                    }
                }
            } else {
                _pending = null;
                _status = "Keine Frage offen";
            }
        } else {
            _pending = null;
            _status = RelayClient.describe(code);
        }
        WatchUi.requestUpdate();
    }

    public function getPending() as Dictionary? {
        return _pending;
    }

    //! Send the chosen option; hide the question right away.
    public function answer(id as String, index as Number) as Void {
        _answeredId = id;
        _pending = null;
        _status = "Sende...";
        _client.sendAnswer(id, index, method(:onAnswered));
        WatchUi.requestUpdate();
    }

    public function onAnswered(code as Number, data as Dictionary or String or Null) as Void {
        if (code == 200 && data instanceof Dictionary) {
            _status = "Gesendet:\n" + (data["answer"] as String);
        } else {
            _status = RelayClient.describe(code);
        }
        WatchUi.requestUpdate();
    }

    public function onUpdate(dc as Dc) as Void {
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
        dc.clear();
        var cx = dc.getWidth() / 2;
        var maxW = dc.getWidth() * 3 / 4;

        var pending = _pending;
        if (pending == null) {
            drawLines(dc, wrap(dc, _status, Graphics.FONT_SMALL, maxW, 4), Graphics.FONT_SMALL,
                      cx, dc.getHeight() / 3, Graphics.COLOR_WHITE);
            return;
        }

        var y = dc.getHeight() / 8;
        y = drawLines(dc, wrap(dc, pending["title"] as String, Graphics.FONT_SMALL, maxW, 2),
                      Graphics.FONT_SMALL, cx, y, Graphics.COLOR_YELLOW);
        y = drawLines(dc, wrap(dc, pending["description"] as String, Graphics.FONT_XTINY, maxW, 6),
                      Graphics.FONT_XTINY, cx, y + 6, Graphics.COLOR_LT_GRAY);
        dc.setColor(Graphics.COLOR_GREEN, Graphics.COLOR_BLACK);
        dc.drawText(cx, dc.getHeight() - dc.getFontHeight(Graphics.FONT_XTINY) - 22,
                    Graphics.FONT_XTINY, "Enter / Tippen: Antwort", Graphics.TEXT_JUSTIFY_CENTER);
    }

    //! Draws centered lines, returns the y below the last line.
    private function drawLines(dc as Dc, lines as Array<String>, font as FontType, x as Number, y as Number, color as Number) as Number {
        dc.setColor(color, Graphics.COLOR_BLACK);
        var h = dc.getFontHeight(font);
        for (var i = 0; i < lines.size(); i++) {
            dc.drawText(x, y, font, lines[i], Graphics.TEXT_JUSTIFY_CENTER);
            y += h;
        }
        return y;
    }

    //! Greedy character wrap (commands and paths have no spaces to break on).
    private function wrap(dc as Dc, text as String, font as FontType, maxW as Number, maxLines as Number) as Array<String> {
        var lines = [] as Array<String>;
        var line = "";
        var chars = text.toCharArray();
        for (var i = 0; i < chars.size(); i++) {
            var c = chars[i];
            if (c == '\n') {
                c = ' ';
            }
            var next = line + c.toString();
            if (dc.getTextWidthInPixels(next, font) > maxW && line.length() > 0) {
                lines.add(line);
                if (lines.size() >= maxLines) {
                    lines[maxLines - 1] = lines[maxLines - 1] + "...";
                    return lines;
                }
                line = c.toString();
            } else {
                line = next;
            }
        }
        if (line.length() > 0) {
            lines.add(line);
        }
        return lines;
    }
}

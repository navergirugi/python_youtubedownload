import Foundation
import PythonKit

enum PyError: LocalizedError {
    case missingBundle(String)
    case python(String)

    var errorDescription: String? {
        switch self {
        case .missingBundle(let p): return "번들에 \(p) 없음"
        case .python(let m): return "Python 오류: \(m)"
        }
    }
}

final class PyBridge {
    private static var started = false

    static func start() throws {
        if started { return }
        let bundle = Bundle.main
        guard let home = bundle.path(forResource: "python", ofType: nil) else {
            throw PyError.missingBundle("python")
        }
        guard let framework = bundle.path(
            forResource: "Python", ofType: "framework", inDirectory: "Frameworks"
        ) else {
            throw PyError.missingBundle("Python.framework")
        }
        let app = bundle.path(forResource: "PythonApp", ofType: nil) ?? ""

        setenv("PYTHONHOME", home, 1)
        if !app.isEmpty { setenv("PYTHONPATH", app, 1) }

        // PythonKit 은 dlopen 으로 인터프리터를 찾는데, xcframework 은 app bundle
        // 안에 임베드돼 있으므로 경로를 직접 알려줘야 한다.
        setenv("PYTHON_LIBRARY", framework, 1)
        try PythonLibrary.useLibrary(at: framework)
        try PythonLibrary.loadLibrary()

        if !app.isEmpty {
            Python.import("sys").path.append(app)
        }
        _ = Python.import("yt_dlp")
        started = true
    }

    static func ytdlpVersion() throws -> String {
        try start()
        let v = Python.import("yt_dlp.version")
        return String(describing: v.__version__)
    }

    /// mdl_ios.dispatch(명령 JSON) 을 호출하고 결과 JSON 문자열을 받는다.
    /// PythonKit 의 list/dict 변환은 형태가 불안정하므로 문자열로 넘겨 Swift 가 디코딩한다.
    static func callJSON(_ name: String, _ args: [String] = []) throws -> String {
        try start()
        let payload: [String: Any] = ["fn": name, "args": args]
        let cmd = try JSONSerialization.data(withJSONObject: payload)
        let cmdStr = String(data: cmd, encoding: .utf8) ?? "{}"
        let raw = String(describing: Python.import("mdl_ios").dispatch(cmdStr))

        // Python 쪽이 {ok, data} / {ok, error} 로 감싸서 돌려준다. 예외를 던지지
        // 않기 때문이다(PythonKit 호출부는 try! 라서 예외가 프로세스를 죽임).
        guard let data = raw.data(using: .utf8),
              let env = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            throw PyError.python("응답 형식 이상: \(raw.prefix(200))")
        }
        if (env["ok"] as? Bool) != true {
            let msg = (env["error"] as? String) ?? "알 수 없는 오류"
            let tb = (env["trace"] as? String) ?? ""
            throw PyError.python(msg + "\n" + tb)
        }
        let inner = try JSONSerialization.data(withJSONObject: env["data"] ?? [])
        return String(data: inner, encoding: .utf8) ?? "[]"
    }
}

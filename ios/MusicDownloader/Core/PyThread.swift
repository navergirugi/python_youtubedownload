import Foundation

/// CPython 인터프리터는 여러 스레드에서 동시에 건드리면 죽는다.
/// 실기기 세그폴트(스레드 1, PyImport_ImportModule 안에서 EXC_BAD_ACCESS)가
/// 그 증거다. 시뮬레이터에서는 운 좋게 같은 스레드에 걸려 통과했다.
///
/// 모든 Python 호출을 여기로 직렬화한다. 스레드는 정확히 하나이며,
/// Py_Initialize 를 포함한 최초 접촉도 이 스레드에서 일어나므로
/// GIL 역시 항상 이 스레드가 쥐고 있다. 중첩 호출은 금지(데드락).
final class PyThread {
    static let shared = PyThread()

    private var worker: Thread!
    private var pending: [() -> Void] = []
    private let lock = NSLock()
    private let hasWork = DispatchSemaphore(value: 0)

    private init() {
        worker = Thread { [weak self] in self?.loop() }
        worker.name = "mdl-python"
        // 2차 스레드 기본 스택(512KB)에서는 import 체인이 터질 수 있어 8MB로.
        worker.stackSize = 8 * 1024 * 1024
        worker.start()
    }

    private func loop() {
        while true {
            hasWork.wait()
            lock.lock()
            let next = pending.isEmpty ? nil : pending.removeFirst()
            lock.unlock()
            next?()
        }
    }

    func sync<T>(_ body: @escaping () throws -> T) throws -> T {
        var boxed: Result<T, Error>?
        let done = DispatchSemaphore(value: 0)
        lock.lock()
        pending.append {
            boxed = Result(catching: body)
            done.signal()
        }
        lock.unlock()
        hasWork.signal()
        done.wait()
        guard let boxed else { throw PyError.python("내부 동기화 오류") }
        return try boxed.get()
    }
}

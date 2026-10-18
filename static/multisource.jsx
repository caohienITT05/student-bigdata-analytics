/* Five UI sections with source analysis and full-course OULAD activity. */
(function () {
    const {useState, useEffect, useRef} = React;
    const nf = new Intl.NumberFormat('vi-VN', {maximumFractionDigits: 2});
    const fmt = value => value === null || value === undefined ? '—' : typeof value === 'number' ? nf.format(value) : String(value);
    const sourceNames = {original: 'Gốc · quan sát', kaggle_train: 'Kaggle train · sinh', kaggle_test: 'Kaggle test · sinh'};
    const colors = ['#4f46e5', '#0d9488', '#f59e0b', '#e11d48'];
    const box = 'bg-white border border-slate-200 rounded-xl p-4';
    const qs = values => new URLSearchParams(values).toString();
    const ActivePanel = React.createContext(false);
    const routes = [['overview', 'Tổng quan'], ['academic', 'Kết quả học tập'], ['oulad', 'Hành vi OULAD'],
                    ['prediction', 'Dự đoán & tra cứu'], ['quality', 'Chất lượng dữ liệu']];

    function useResult(path) {
        const [state, setState] = useState({data: null, error: '', loading: true});
        useEffect(() => {
            const controller = new AbortController();
            setState({data: null, error: '', loading: true});
            fetch(path, {signal: controller.signal}).then(async res => {
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Không tải được kết quả');
                return data;
            }).then(data => setState({data, error: '', loading: false})).catch(error => {
                if (error.name !== 'AbortError') setState({data: null, error: error.message, loading: false});
            });
            return () => controller.abort();
        }, [path]);
        return state;
    }

    function Selector({title, value, options, onChange}) {
        return <label className="flex flex-col gap-1 text-xs text-slate-600"><span>{title}</span>
            <select aria-label={title} value={value} onChange={e => onChange(e.target.value)} className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white text-slate-800">
                {options.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </select></label>;
    }
    function Metric({label, value, detail}) {
        return <div className={box}><p className="text-xs text-slate-500">{label}</p><p className="text-2xl font-semibold mt-1 text-indigo-950">{fmt(value)}</p><p className="text-xs text-slate-500 mt-1">{detail}</p></div>;
    }
    function Table({rows, columns}) {
        return <div className="overflow-x-auto"><table className="w-full text-sm text-left"><thead className="bg-slate-50 text-slate-600"><tr>{columns.map(([key, title]) => <th key={key} className="px-3 py-2 whitespace-nowrap">{title}</th>)}</tr></thead>
            <tbody className="divide-y divide-slate-100">{rows.length ? rows.map((row, index) => <tr key={index}>{columns.map(([key]) => <td key={key} className="px-3 py-2 whitespace-nowrap">{key === 'source' ? sourceNames[row[key]] : fmt(row[key])}</td>)}</tr>) : <tr><td colSpan={columns.length} className="p-4 text-slate-500">Không có kết quả trong bộ lọc này.</td></tr>}</tbody></table></div>;
    }
    function ChartPanel({title, note, type = 'bar', labels, datasets}) {
        const canvas = useRef(null);
        const active = React.useContext(ActivePanel);
        const signature = JSON.stringify({type, labels, datasets});
        useEffect(() => {
            if (!active || !canvas.current || !labels.length) return;
            const chart = new Chart(canvas.current, {type, data: {labels, datasets}, options: {responsive: true, maintainAspectRatio: false,
                animation: false, plugins: {legend: {position: 'bottom', labels: {boxWidth: 10, font: {size: 12}}}},
                scales: {y: {beginAtZero: true, title: {display: true, text: type === 'line' ? 'Lượt nhấp' : 'Bản ghi / lượt học'}}}}});
            return () => chart.destroy();
        }, [signature, active]);
        return <div className={box + ' min-w-0'}><h3 className="font-semibold text-base">{title}</h3><p className="text-sm text-slate-500 mt-1 mb-3">{note}</p><div className="h-64 min-w-0">{labels.length ? <canvas ref={canvas} aria-label={title} role="img"/> : <p className="text-sm text-slate-500">Không có dữ liệu.</p>}</div></div>;
    }
    function grouped(rows, labelKey, valueKey, groupKey = 'source') {
        const labels = [...new Set(rows.map(r => r[labelKey] === null ? 'Không có nhãn' : r[labelKey]))];
        const groups = [...new Set(rows.map(r => r[groupKey]))];
        return {labels, datasets: groups.map((group, index) => ({label: sourceNames[group] || group,
            data: labels.map(label => rows.filter(r => r[groupKey] === group && (r[labelKey] === null ? 'Không có nhãn' : r[labelKey]) === label).reduce((sum, row) => sum + row[valueKey], 0)),
            backgroundColor: colors[index % colors.length], borderColor: colors[index % colors.length], tension: 0.2}))};
    }
    function Pager({result, number, onChange, unit = 'dòng tổng hợp'}) {
        if (!result) return null;
        return <div className="flex flex-wrap justify-between items-center gap-3 mt-3 text-xs text-slate-500"><span>{fmt(result.total)} {unit} · trang {number}/{Math.max(1, result.pages)}</span>
            <div className="flex gap-2"><button className="border rounded-lg px-3 py-1 disabled:opacity-40" disabled={number <= 1} onClick={() => onChange(number - 1)}>Trang trước</button><button className="border rounded-lg px-3 py-1 disabled:opacity-40" disabled={number >= result.pages} onClick={() => onChange(number + 1)}>Trang sau</button></div></div>;
    }
    function Loading({state}) {
        if (state.error) return <p role="alert" className="p-4 bg-rose-50 text-rose-800 rounded-lg text-sm">{state.error}</p>;
        if (state.loading) return <p className="p-4 text-slate-500 text-sm" role="status">Đang đọc bảng kết quả…</p>;
        return null;
    }
    function PagedTable({rows, columns, resetKey, size = 8}) {
        const [number, setNumber] = useState(1);
        useEffect(() => setNumber(1), [resetKey]);
        const pages = Math.ceil(rows.length / size), current = Math.min(number, Math.max(1, pages));
        return <><Table rows={rows.slice((current - 1) * size, current * size)} columns={columns}/>
            <Pager result={{total: rows.length, pages}} number={current} onChange={setNumber}/></>;
    }
    function Detail({title, note, children, open = false}) {
        return <details className={box} open={open}><summary className="cursor-pointer font-semibold text-base">{title}</summary>
            {note && <p className="text-sm text-slate-500 my-3">{note}</p>}<div className="mt-3">{children}</div></details>;
    }

    function Academic() {
        const [source, setSource] = useState('all');
        const filters = qs({source});
        const result = useResult('/api/multi/academic/summary?' + filters);
        const d = result.data;
        return <div className="space-y-4">
            <div className="flex flex-wrap gap-3">
                <Selector title="Nguồn nhánh A" value={source} onChange={setSource} options={[['all', 'Tất cả nguồn'], ...Object.entries(sourceNames)]}/>
            </div>
            <p className="text-xs text-slate-500">UNION mọi đặc trưng của ba file, giữ nguồn riêng. Tổng là bản ghi, không phải số sinh viên thật. Target test luôn trống; biểu đồ này dùng nhãn dữ liệu, không dùng dự đoán model cũ.</p>
            <Loading state={result}/>
            {d && <>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3"><Metric label="Tổng bản ghi" value={d.totals.records} detail={'Có nhãn: ' + fmt(d.totals.labelled)}/><Metric label="Bản ghi quan sát" value={d.totals.observed} detail="Dataset gốc"/><Metric label="Bản ghi dữ liệu sinh" value={d.totals.synthetic} detail="Kaggle train và test"/><Metric label="Chưa có Target" value={d.totals.unlabelled} detail={'Bản ghi có cờ lỗi: ' + fmt(d.totals.flagged)}/></div>
                <div className={box}><h3 className="text-sm font-semibold mb-2">Đối chiếu nguồn và nhãn</h3><Table rows={d.sources} columns={[
                    ['source','Nguồn'],['source_file','File nguồn'],['records','Bản ghi'],['labelled_records','Có nhãn'],['dropout_records','Target Dropout'],['dropout_percent','Dropout / có nhãn (%)'],['mean_age','TB tuổi'],['mean_sem1','TB HK1'],['mean_sem2','TB HK2']]}/></div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <ChartPanel title="Phân bố Target theo nguồn" note="Kết quả trong dữ liệu, không phải dự đoán. Thiếu nhãn được hiển thị riêng." {...grouped(d.targets, 'target', 'records')}/>
                    {[['age', 'Phân bố tuổi'], ['sem1_grade', 'Điểm học kỳ 1'], ['sem2_grade', 'Điểm học kỳ 2']].map(([metric, title]) => <ChartPanel key={metric} title={title} note={metric === 'age' ? 'Tuổi tại nhập học · số bản ghi / khoảng tuổi' : 'Điểm thang 0–20 · điểm 0 được giữ riêng'} {...grouped(d.histograms.filter(r => r.metric === metric), 'bin', 'records')}/>)}
                </div>
            </>}
        </div>;
    }

    function Oulad({status}) {
        const [module, setModule] = useState('all'), [presentation, setPresentation] = useState('all');
        const result = useResult('/api/multi/oulad/summary?' + qs({module, presentation}));
        const d = result.data, p = d && d.population;
        return <div className="space-y-4">
            <div className="flex flex-wrap gap-3"><Selector title="Học phần OULAD" value={module} onChange={setModule} options={[['all','Tất cả học phần'], ...status.modules.map(x => [x,x])]}/><Selector title="Đợt học OULAD" value={presentation} onChange={setPresentation} options={[['all','Tất cả đợt'], ...status.presentations.map(x => [x,x])]}/></div>
            <p className="text-sm text-slate-600">Người học được đếm duy nhất; một người có thể có nhiều lượt học (học phần + đợt). Lượt nhấp là số lần tương tác được ghi, không phải số người. Withdrawn = rút học phần; Fail = không đạt; Pass = đạt; Distinction = đạt mức xuất sắc.</p>
            <p className="text-xs text-indigo-800 bg-indigo-50 p-3 rounded-lg">Phạm vi: cả học phần. Kết quả cuối dùng để mô tả hồi cứu; không phải dự đoán sớm hay kết luận nhân quả.</p>
            <Loading state={result}/>
            {d && !p && <p className={box}>Không có lượt học trong học phần/đợt đã chọn.</p>}
            {p && <>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3"><Metric label="Lượt học" value={p.enrolments} detail="Giữ lượt không có sự kiện"/><Metric label="Người học duy nhất" value={p.unique_learners} detail="Không cộng số duy nhất giữa học phần"/><Metric label="Tổng lượt nhấp" value={p.clicks} detail={'Không xác định: ' + fmt(p.clicks_undefined_enrolments) + ' lượt học'}/><Metric label="Lượt học không tương tác" value={p.no_activity_enrolments} detail="Không có sự kiện cả học phần"/></div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4"><ChartPanel title="Kết quả cuối cùng của lượt học" note="Nhãn gốc OULAD · số lượt học, khác nhãn thôi học đại học" labels={d.outcomes.map(r => r.final_result)} datasets={[{label:'Lượt học',data:d.outcomes.map(r => r.enrolments),backgroundColor:colors}]}/>
                    <ChartPanel title="Hoạt động theo tuần và nhóm kết quả về sau" note="Tuần = floor(ngày / 7); tuần âm là trước ngày 0. Tổng lượt nhấp trong từng tuần của cả học phần." type="line" {...grouped(d.weekly, 'week', 'clicks', 'final_result')}/></div>
                <Detail title="Hoạt động và kết quả theo nhóm"><Table rows={d.outcomes} columns={[
                    ['final_result','Kết quả cuối'],['enrolments','Lượt học'],['enrolment_percent','Tỷ lệ (%)'],['mean_clicks','TB nhấp/lượt'],['mean_active_days','TB ngày hoạt động'],['mean_resources','TB tài nguyên'],['pre_start_clicks','Nhấp trước ngày 0'],['no_activity_enrolments','Không tương tác']]}/></Detail>
            </>}
        </div>;
    }

    function Overview({status, navigate}) {
        const academic = useResult('/api/multi/academic/summary');
        const oulad = useResult('/api/multi/oulad/summary');
        const a = academic.data, p = oulad.data && oulad.data.population;
        const sourceCount = name => a ? a.sources.filter(row => row.source === name).reduce((sum, row) => sum + row.records, 0) : null;
        return <div className="space-y-5">
            <div className="rounded-xl bg-indigo-50 border border-indigo-100 p-5">
                <h3 className="text-lg font-semibold text-indigo-950">Kết quả học tập và hành vi học tập từ nhiều nguồn</h3>
                <p className="text-sm text-indigo-900 mt-2">So sánh phân bố kết quả của dataset gốc và Kaggle, khám phá hoạt động OULAD theo thời gian, và tra cứu dự đoán từ mô hình cũ. Mỗi nguồn có đơn vị riêng; không cộng thành tổng số sinh viên thật.</p>
            </div>
            <Loading state={academic}/><Loading state={oulad}/>
            {a && p && <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <Metric label="Dataset gốc · bản ghi quan sát" value={a.totals.observed} detail="Giữ kết quả Target trong dữ liệu gốc"/>
                <Metric label="Kaggle · bản ghi dữ liệu sinh" value={a.totals.synthetic} detail={'Train: ' + fmt(sourceCount('kaggle_train')) + ' · Test: ' + fmt(sourceCount('kaggle_test')) + ' (Target trống)'}/>
                <Metric label="OULAD · lượt học" value={p.enrolments} detail={fmt(p.unique_learners) + ' người học duy nhất · ' + fmt(status.quality.joins.input_vle_rows) + ' dòng tương tác'}/>
            </div>}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{[
                ['academic','So sánh kết quả học tập','Target, tuổi, điểm hai học kỳ và các chỉ số học tập, tách theo nguồn.'],
                ['oulad','Khám phá hành vi OULAD','Lượt học, người học, lượt nhấp, kết quả học phần và hoạt động theo tuần trong cả học phần.'],
                ['prediction','Dự đoán và tra cứu sinh viên','Dùng model hiện có, phân biệt nhãn dữ liệu với dự đoán của mô hình.'],
                ['quality','Kiểm tra chất lượng dữ liệu','Ô thiếu, dòng trùng, khóa JOIN và báo cáo nguồn.']
            ].map(([key, title, note]) => <div key={key} className={box}><h3 className="font-semibold text-base">{title}</h3><p className="text-sm text-slate-500 mt-2 mb-4">{note}</p><button className="text-sm font-medium text-indigo-700 rounded-lg border border-indigo-200 px-3 py-2 hover:bg-indigo-50" onClick={() => navigate(key)}>Mở {routes.find(row => row[0] === key)[1].toLowerCase()} →</button></div>)}</div>
        </div>;
    }

    function DataExplorer() {
        const result = useResult('/api/multi/catalog');
        const [sourceKey, setSourceKey] = useState('original'), [fileKey, setFileKey] = useState('original');
        const [group, setGroup] = useState('all'), [page, setPage] = useState(1);
        const data = result.data;
        const source = data && data.sources.find(row => row.key === sourceKey);
        const file = source && (source.files.find(row => row.key === fileKey) || source.files[0]);
        const fields = file ? file.fields.filter(row => group === 'all' || row.group === group) : [];
        const pages = Math.ceil(fields.length / 8), current = Math.min(page, Math.max(1, pages));
        const selectSource = key => {setSourceKey(key); setFileKey(''); setGroup('all'); setPage(1);};
        const selectFile = key => {setFileKey(key); setGroup('all'); setPage(1);};
        const selectGroup = key => {setGroup(key); setPage(1);};
        return <section className={box} aria-label="Khám phá dữ liệu sử dụng">
            <h3 className="font-semibold text-base">Dữ liệu sử dụng có những gì?</h3>
            <Loading state={result}/>
            {data && <>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 my-4" aria-label="Chọn nguồn dữ liệu">
                    {data.sources.map(row => <button type="button" key={row.key} aria-pressed={sourceKey === row.key}
                        onClick={() => selectSource(row.key)} className={'text-left p-3 rounded-lg border transition-colors ' +
                            (sourceKey === row.key ? 'border-indigo-500 bg-indigo-50' : 'border-slate-200 bg-white hover:bg-slate-50')}>
                        <span className="flex justify-between items-center font-medium text-sm"><span>{row.label}</span>{sourceKey === row.key && <span className="text-indigo-600" aria-hidden="true">✓</span>}</span>
                        <span className="block text-xs text-slate-500 mt-1">{row.detail}</span>
                    </button>)}
                </div>
                {file && <>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
                        <Selector title="File dữ liệu" value={file.key} onChange={selectFile} options={source.files.map(row => [row.key, row.name])}/>
                        <Selector title="Nhóm thông tin" value={group} onChange={selectGroup} options={[
                            ['all', 'Tất cả nhóm thông tin'], ...[...new Set(file.fields.map(row => row.group))].map(key => [key, data.groups[key]])]}/>
                    </div>
                    <div className="flex flex-wrap justify-between items-center gap-2 text-sm">
                        <code className="font-medium break-all">{file.name}</code>
                        <span className="text-slate-500">{fmt(file.rows)} dòng · {fmt(file.column_count)} cột</span>
                    </div>
                    <p className="text-sm text-slate-600 bg-indigo-50 rounded-lg px-3 py-2 my-3">{file.note}</p>
                    <table className="w-full table-fixed text-sm text-left" aria-label="Các trường trong dữ liệu">
                        <thead className="bg-slate-50 text-slate-600"><tr>
                            <th className="w-1/3 md:w-[28%] px-2 py-2 font-medium">Thông tin</th>
                            <th className="w-1/3 md:w-[30%] px-2 py-2 font-medium">Tên cột trong file</th>
                            <th className="px-2 py-2 font-medium">Dạng dữ liệu</th>
                            <th className="hidden md:table-cell w-[17%] px-2 py-2 font-medium">Nhóm</th>
                        </tr></thead>
                        <tbody className="divide-y divide-slate-100">{fields.slice((current - 1) * 8, current * 8).map(row => <tr key={row.key}>
                            <td className="px-2 py-3 break-words">{row.label}</td>
                            <td className="px-2 py-3"><code className="text-xs text-slate-500 [overflow-wrap:anywhere]">{row.key}</code></td>
                            <td className="px-2 py-3 break-words">{row.type}</td>
                            <td className="hidden md:table-cell px-2 py-3 text-slate-500 break-words">{data.groups[row.group]}</td>
                        </tr>)}</tbody>
                    </table>
                    <div aria-live="polite"><Pager result={{total: fields.length, pages}} number={current} onChange={setPage} unit="trường"/></div>
                </>}
            </>}
        </section>;
    }

    function Quality({status, reload}) {
        const joinNames = {
            enrolment_key:'Khóa lượt học', cardinality:'Quy tắc JOIN', input_vle_rows:'Dòng VLE đầu vào', joined_vle_rows:'Dòng VLE sau JOIN',
            vle_without_enrolment:'VLE thiếu hồ sơ lượt học', vle_without_resource:'VLE thiếu tài nguyên',
            assessment_without_definition:'Bài nộp thiếu định nghĩa', assessment_without_enrolment:'Bài nộp thiếu hồ sơ',
            registration_without_profile:'Đăng ký thiếu hồ sơ', profiles_without_registration:'Hồ sơ thiếu đăng ký', profiles_without_course:'Hồ sơ thiếu học phần',
            enrolments:'Lượt học giữ lại', unique_learners:'Người học duy nhất', no_vle_entire_course:'Không tương tác cả kỳ'
        };
        const joins = Object.entries(status.quality.joins).map(([key, value]) => ({metric:joinNames[key] || key, value}));
        return <div className="space-y-4">
            <DataExplorer/>
            <p className="text-sm text-slate-600">Giữ nguyên mọi dòng và điểm 0; không điền trung bình hoặc tự xóa dòng giống nhau. Báo cáo dưới đây có phạm vi toàn bộ dữ liệu, độc lập với bộ lọc phân tích.</p>
            <Detail title="Chất lượng theo nguồn và file">
                <PagedTable rows={status.quality.sources} columns={[
                    ['file','Nguồn/file'],['rows','Dòng'],['columns','Cột'],['missing_cells','Ô thiếu gốc'],['flagged_rows','Dòng có cờ'],
                    ['full_row_duplicate_excess','Dòng trùng dư'],['duplicate_key_excess','Khóa trùng dư'],['missing_key_rows','Dòng thiếu khóa'],['key','Khóa kiểm tra']]}/>
            </Detail>
            <Detail title="Chi tiết kỹ thuật" note={status.mode}>
                <h3 className="font-semibold text-base mb-3">Kiểm tra JOIN</h3>
                <PagedTable rows={joins} columns={[["metric","Kiểm tra"],["value","Kết quả"]]} size={10}/>
                <h3 className="font-semibold text-base mt-5 mb-3">Thông tin Spark và file kết quả</h3>
                <p className="text-sm mb-3">Xuất kết quả: {new Date(status.metadata.processed_at).toLocaleString('vi-VN', {timeZone:'Asia/Ho_Chi_Minh'})} · File: <code>{status.metadata.database}</code></p>
                <Table rows={['a','oulad','sql'].map(key => {const run = status.runs[key], r = run.runtime; return {
                    branch:{a:'Kết quả học tập',oulad:'OULAD',sql:'Spark SQL'}[key],seconds:run.elapsed_seconds,spark:r.spark_version,
                    master:r.master,driver:r.driver_memory,shuffle:r.shuffle_partitions,partition:r.max_partition_bytes,
                    completed:new Date(run.completed_at).toLocaleString('vi-VN', {timeZone:'Asia/Ho_Chi_Minh'})};})} columns={[
                    ['branch','Bước'],['seconds','Giây'],['spark','Spark'],['master','Chế độ'],['driver','Bộ nhớ driver'],['shuffle','Shuffle'],['partition','Partition đọc (byte)'],['completed','Hoàn thành']]}/>
                <p className="text-sm text-slate-500 my-3">Spark chạy local trên một máy. API chỉ đọc các bảng tổng hợp; không xử lý lại Spark khi xem dashboard.</p>
                <PagedTable rows={Object.entries(status.metadata.tables).map(([table, data]) => ({table,rows:data.rows,file:data.sql_file}))}
                    columns={[["table","Bảng kết quả"],["rows","Dòng tổng hợp"],["file","Truy vấn nguồn"]]}/>
                <button className="text-sm border rounded-lg px-3 py-2 mt-3" onClick={reload}>Đọc lại kết quả</button>
            </Detail>
        </div>;
    }

    function currentRoute() {
        const key = window.location.hash.slice(1);
        return routes.some(row => row[0] === key) ? key : 'overview';
    }
    function MultiSourceDashboard({PredictionPanel}) {
        const [section, setSection] = useState(currentRoute), [reload, setReload] = useState(0);
        const activeButton = useRef(null);
        const state = useResult('/api/multi/status?refresh=' + reload), s = state.data;
        useEffect(() => {
            const onHash = () => setSection(currentRoute());
            window.addEventListener('hashchange', onHash);
            if (window.location.hash !== '#' + currentRoute()) window.history.replaceState(null, '', '#' + currentRoute());
            return () => window.removeEventListener('hashchange', onHash);
        }, []);
        React.useLayoutEffect(() => {
            window.scrollTo({top:0, left:0, behavior:'auto'});
            if (activeButton.current) activeButton.current.scrollIntoView({block:'nearest', inline:'nearest'});
        }, [section]);
        const navigate = key => {
            if (key === section) window.scrollTo({top:0, left:0, behavior:'auto'});
            else {setSection(key); window.location.hash = key;}
        };
        const keyboardNavigation = event => {
            if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
            const buttons = [...event.currentTarget.querySelectorAll('[role="tab"]')];
            const index = buttons.indexOf(event.target);
            if (index < 0) return;
            event.preventDefault();
            const next = event.key === 'Home' ? 0 : event.key === 'End' ? routes.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + routes.length) % routes.length;
            buttons[next].focus(); navigate(routes[next][0]);
        };
        return <div className="min-h-screen">
            <div className="sticky top-0 z-30 bg-white border-b border-slate-200 shadow-sm" data-dashboard-header>
                <header className="max-w-7xl mx-auto px-4 sm:px-6 py-3"><h1 className="text-xl font-bold text-slate-900">Phân tích dữ liệu giáo dục</h1><p className="text-sm text-slate-500 mt-1">Kết quả học tập · Hành vi OULAD · Dự đoán và tra cứu</p></header>
                <nav className="dashboard-nav max-w-7xl mx-auto px-4 sm:px-6 overflow-x-auto" aria-label="Điều hướng dashboard">
                    <div role="tablist" aria-label="Các mục dashboard" className="flex w-max min-w-full gap-1" onKeyDown={keyboardNavigation}>
                        {routes.map(([key, title]) => <button key={key} ref={section === key ? activeButton : null} id={'nav-' + key} role="tab"
                            aria-selected={section === key} aria-controls={'panel-' + key} tabIndex={section === key ? 0 : -1} onClick={() => navigate(key)}
                            className={'shrink-0 whitespace-nowrap px-4 py-3 border-b-2 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-indigo-500 ' +
                                (section === key ? 'text-indigo-700 bg-indigo-50 border-indigo-600' : 'text-slate-600 border-transparent hover:bg-slate-50')}>{title}</button>)}
                    </div>
                </nav>
            </div>
            <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
                {section !== 'prediction' && <><Loading state={state}/>{s && !s.ready && <p className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-sm text-amber-900">{s.message}</p>}</>}
                {routes.map(([key, title]) => <ActivePanel.Provider key={key} value={section === key}>
                    <section id={'panel-' + key} role="tabpanel" aria-labelledby={'nav-' + key} hidden={section !== key} className="dashboard-panel space-y-4">
                        <h2 className="text-xl font-bold text-slate-900">{title}</h2>
                        {key === 'prediction' && <PredictionPanel active={section === key}/>}
                        {s && s.ready && key === 'overview' && <Overview status={s} navigate={navigate}/>}
                        {s && s.ready && key === 'academic' && <Academic/>}
                        {s && s.ready && key === 'oulad' && <Oulad status={s}/>}
                        {s && s.ready && key === 'quality' && <Quality status={s} reload={() => setReload(reload + 1)}/>}
                    </section>
                </ActivePanel.Provider>)}
            </main>
        </div>;
    }
    window.DashboardPager = Pager;
    window.MultiSourceDashboard = MultiSourceDashboard;
})();

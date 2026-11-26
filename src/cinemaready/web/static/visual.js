function renderVisual(target, data) {
    const rows = data.rows.filter(row => row.state !== '观察').slice(0,5);
    const scale = Math.max(40,Math.ceil(Math.max(...rows.map(row => row.estimate))/10)*10);
    const axis = node('div',undefined,'axis');
    for (let tick = 0; tick <= 4; tick++) axis.append(node('span',`${scale*tick/4} 分`));
    target.append(axis);
    for (const slot of rows) {
        const track = node('div',undefined,'track');
        const title = node('button',slot.key,'item-link');
        title.addEventListener('click',() => inspect(slot));
        const bar = node('div',undefined,'track-meter');
        const duration = node('i');
        duration.style.width = `${slot.estimate/scale*100}%`;
        const available = node('b');
        available.style.left = `${Math.min(100,(slot.measurements.minutes||0)/scale*100)}%`;
        bar.append(duration,available);
        bar.title = `清场估计 ${format.format(slot.estimate)} 分 · 场间 ${slot.measurements.minutes ?? '未报'} 分`;
        track.append(title,bar);
        target.append(track);
    }
    target.append(node('p','实线为清场估计，虚线标注场间可用时间。','timeline-caption'));
}

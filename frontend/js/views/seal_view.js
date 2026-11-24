export const sealViewTemplate = `
<section class="panel">
  <h2>闸代快照</h2>
  <p class="hint">封闸升代并写入清单摘要，供提单册对账引用。旁路开放未闭环时封闸只落影子草稿，正式快照零增，待旁路闭合自动原子晋升。</p>
  <div class="form-row">
    <div><label>过磅票</label>
      <select v-model.number="sealForm.ticket_id">
        <option v-for="t in sealableTickets" :key="t.id" :value="t.id">{{ t.ticket_code }} · {{ t.status }}</option>
      </select>
    </div>
    <div><label>清单(可空)</label><input v-model="sealForm.manifest"/></div>
  </div>
  <p v-if="sealBlockedByHold" class="action-err">旁路开放禁封：当前票仍有开放超重挂起，封闸只会落影子草稿，须先闭环旁路。</p>
  <div class="actions">
    <button @click="createSeal">写入快照</button>
    <button class="secondary" @click="refresh">刷新</button>
  </div>
  <table class="data-table">
    <thead><tr><th>快照号</th><th>票号</th><th>闸代</th><th>清单摘要</th><th>状态</th></tr></thead>
    <tbody>
      <tr v-for="s in seals" :key="s.id">
        <td>{{ s.seal_ref }}</td>
        <td>{{ s.ticket_code }}</td>
        <td>{{ s.ticket_generation }}</td>
        <td class="mono">{{ shortText(s.manifest) }}</td>
        <td><span class="badge pass">{{ s.status }}</span></td>
      </tr>
    </tbody>
  </table>
  <h3>影子草稿（旁路未结，待晋升）</h3>
  <p class="hint">草稿不计入正式快照数；旁路闭环时原子晋升为正式快照。</p>
  <table class="data-table compact">
    <thead><tr><th>草稿号</th><th>票号</th><th>拟闸代</th><th>状态</th><th>请求人</th></tr></thead>
    <tbody>
      <tr v-for="d in sealDrafts" :key="d.id">
        <td class="mono">{{ d.draft_ref }}</td>
        <td>{{ d.ticket_code }}</td>
        <td>{{ d.ticket_generation }}</td>
        <td><span class="badge warn">{{ d.status }}</span></td>
        <td>{{ d.requested_by }}</td>
      </tr>
    </tbody>
  </table>
</section>
`;
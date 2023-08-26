// Define your Vue component
Vue.component('contests-table', {
  data() {
    return {
      contests: [],
      page: 1,
    };
  },
  computed: {
    displayedContests() {
      const pageSize = 2;
      const start = (this.page - 1) * pageSize;
      const end = start + pageSize;
      return this.contests.slice(start, end);
    },
  },
  
  methods: {
    toMarkdown(text) {
      return marked(text);
    },
    nextPage() {
      if (this.page * 2 < this.contests.length) {
        this.page++;
      }
    },
    prevPage() {
      if (this.page > 1) {
        this.page--;
      }
    },
    async saveChanges(contest) {
      try {
        const response = await fetch(`http://localhost:3000/contests/${contest.id}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(contest),
        });
        const result = await response.json();
        console.log('Updated contest:', result);
      } catch (error) {
        console.error('Error updating contest:', error);
      }
    },
  },

  async mounted() {
      try {
        const response = await fetch('http://localhost:3000/contests');
        console.log('Fetched data:', this.contests);
        this.contests = await response.json();
      } catch (error) {
        console.error('Error fetching data:', error);
    }
  },
  
  template: `
  <div id="chartpanel" class="row" data-equalizer>
      <div class="column small-12 left_panel">
          <header data-equalizer-watch>
              <i class="fa fa-bars menu_top_icon" aria-hidden="true"></i>
              <div class="right_nav">
              <i class="fa fa-heart" aria-hidden="true"></i>
              <i class="fa fa-link" aria-hidden="true"></i>
              <i class="fa fa-user-circle" aria-hidden="true"></i>
                  </div>
              <charttitle>Contest Planner by Week with Templates</charttitle>
          </header>
          <div id="chart_table">
              <form id="table_form">
                  <table id="dataTable">
                      <thead>
                          <tr>
                              <th>Week</th>
                              <th>Monday</th>
                              <th>Tuesday</th>
                              <th>Wednesday</th>
                              <th>Thursday</th>
                              <th>Friday</th>
                              <th>Saturday</th>
                              <th>Sunday</th>
                              <th>Action</th>
                          </tr>
                      </thead>
                      <tbody>
                        <tr v-for="contest in displayedContests" :key="contest.id">
                          <td>{{ contest.week }}</td>
                          <td><textarea v-model="contest.monday" rows="4" style="width: 100%;"></textarea><div v-html="toMarkdown(contest.monday)"></div></td>
                          <td><textarea v-model="contest.tuesday" rows="4" style="width: 100%;"></textarea><div v-html="toMarkdown(contest.tuesday)"></div></td>
                          <td><textarea v-model="contest.wednesday" rows="4" style="width: 100%;"></textarea><div v-html="toMarkdown(contest.wednesday)"></div></td>
                          <td><textarea v-model="contest.thursday" rows="4" style="width: 100%;"></textarea><div v-html="toMarkdown(contest.thursday)"></div></td>
                          <td><textarea v-model="contest.friday" rows="4" style="width: 100%;"></textarea><div v-html="toMarkdown(contest.friday)"></div></td>
                          <td><textarea v-model="contest.saturday" rows="4" style="width: 100%;"></textarea><div v-html="toMarkdown(contest.saturday)"></div></td>
                          <td><textarea v-model="contest.sunday" rows="4" style="width: 100%;"></textarea><div v-html="toMarkdown(contest.sunday)"></div></td>
                          <td><button @click="saveChanges(contest)">Save</button></td>
                        </tr>
                      </tbody>
                  </table>
                  <button type="button" @click="prevPage">Previous</button>
                  <button type="button" @click="nextPage">Next</button>
              </form>
          </div>
      </div>
  </div>
  `,
});

// Initialize Vue app
new Vue({
  el: '#app',
  template: '<contests-table />',
});
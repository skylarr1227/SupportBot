

// Initialize Supabase

// Define your Vue component
Vue.component('contests-table', {
    data() {
      return {
        contests: [],
      };
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
                              <th>ID</th>
                              <th>Created At</th>
                              <th>Monday</th>
                              <th>Tuesday</th>
                              <th>Wednesday</th>
                              <th>Thursday</th>
                              <th>Friday</th>
                              <th>Saturday</th>
                              <th>Sunday</th>
                              <th>Week</th>
                              
                          </tr>
                      </thead>
                      <tbody>
                        <tr v-for="contest in contests" :key="contest.id">
                          <td>{{ contest.id }}</td>
                          <td>{{ contest.created_at }}</td>
                          <td>{{ contest.monday }}</td>
                          <td>{{ contest.tuesday }}</td>
                          <td>{{ contest.wednesday }}</td>
                          <td>{{ contest.thursday }}</td>
                          <td>{{ contest.friday }}</td>
                          <td>{{ contest.saturday }}</td>
                          <td>{{ contest.sunday }}</td>
                          <td>{{ contest.week }}</td>
                          <td>

                          </td>
                          </tr>
                        </tbody>
                  </table>
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
